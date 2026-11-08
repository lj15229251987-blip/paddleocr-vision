#!/usr/bin/env python3
"""PaddleOCR hosted API (AI Studio) -> files on disk.

Parses documents/images via Baidu's hosted PaddleOCR API using the official
synchronous client shipped in the `paddleocr` package (same service the
PaddleOCR MCP server wraps). Results (Markdown + images, or plain OCR text)
are written NEXT TO the source document (or to --out DIR), so nothing bulky
ever enters the conversation context.

Run inside the uv-managed env (paddleocr is NOT installed system-wide):
  uv run --python 3.12 --with paddleocr-mcp --no-project python ocr_to_files.py <inputs...> [options]

Token resolution order:
  1. env PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN (or PADDLEOCR_ACCESS_TOKEN)
  2. plugin mcp_config.json (relative to this script or in ~/.gemini/config/plugins/paddleocr-vision/)
  3. ~/.gemini/config/mcp_config.json
  4. ~/.zcode/cli/config.json -> mcp.servers -> paddleocr-vl / paddleocr-ocr
  5. ~/.claude.json -> mcpServers -> paddleocr-vl / paddleocr-ocr
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# Ensure stdout/stderr use UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

IMG_TAG = re.compile(r'<img[^>]+src="([^"]+)"[^>]*>')
DATA_URL = re.compile(r"^data:image/(\w+)[;,]")

try:  # light-weight imports only: paddleocr 3.7 exposes the API client w/o paddle
    from paddleocr import PaddleOCRClient, Model, OCROptions, PaddleOCRVLOptions
except ImportError:  # pragma: no cover - fallback to private modules
    from paddleocr._api_client.client import PaddleOCRClient
    from paddleocr._api_client.models import Model, OCROptions, PaddleOCRVLOptions


# --------------------------------------------------------------------------- utils
def extract_token_from_dict(cfg: dict) -> str:
    # Try mcpServers (Gemini / Claude / standard MCP format)
    servers = cfg.get("mcpServers")
    if not isinstance(servers, dict):
        # Try mcp.servers (ZCode format)
        servers = cfg.get("mcp", {}).get("servers") if isinstance(cfg.get("mcp"), dict) else None

    if isinstance(servers, dict):
        for name in ("paddleocr-vl", "paddleocr-ocr"):
            srv = servers.get(name, {})
            if isinstance(srv, dict):
                env = srv.get("env", {})
                tok = env.get("PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN") or env.get("PADDLEOCR_ACCESS_TOKEN") or ""
                if tok and "PASTE" not in tok and "<" not in tok:
                    return tok
    return ""


def resolve_token() -> str:
    # 1. Environment variables
    tok = (
        os.environ.get("PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN")
        or os.environ.get("PADDLEOCR_ACCESS_TOKEN")
        or ""
    )
    if tok:
        return tok

    # Potential config file locations
    candidates = [
        Path(__file__).resolve().parents[2] / "mcp_config.json",
        Path.home() / ".gemini" / "config" / "plugins" / "paddleocr-vision" / "mcp_config.json",
        Path.home() / ".gemini" / "config" / "mcp_config.json",
        Path.home() / ".zcode" / "cli" / "config.json",
        Path.home() / ".claude.json",
    ]

    for p in candidates:
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                found = extract_token_from_dict(data)
                if found:
                    return found
            except Exception:
                continue

    sys.exit("ERROR: no AI Studio token found in environment or local MCP configuration files.")


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def guess_ext(value: str, fallback: str = ".jpg") -> str:
    m = DATA_URL.match(value)
    if m:
        ext = m.group(1).lower()
        return ".jpg" if ext == "jpeg" else f".{ext}"
    suffix = Path(urlparse(value).path).suffix.lower() if is_url(value) else Path(value).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tif", ".tiff"} else fallback


def fetch_image(value: str) -> bytes:
    if is_url(value):
        with urllib.request.urlopen(value, timeout=120) as resp:  # noqa: S310
            return resp.read()
    payload = value.partition(",")[2] if value.startswith("data:") else value
    return base64.b64decode(payload)


class ImageSink:
    """Writes images under one folder with collision-safe names (folder is
    created lazily, so image-less documents leave no empty directories)."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.seen: dict[str, Path] = {}
        self.saved = 0

    def path_for(self, key: str, value: str) -> Path:
        name = Path(urlparse(key).path if is_url(key) else key).name or "img"
        path = self.folder / (name if Path(name).suffix else name + guess_ext(value))
        i = 1
        while path.exists() or any(p == path for p in self.seen.values()):
            path = self.folder / f"{path.stem}_{i}{path.suffix}"
            i += 1
        return path

    def save(self, key: str, value: str) -> Path | None:
        try:
            data = fetch_image(value)
        except Exception as exc:  # noqa: BLE001 - keep parsing, report at end
            print(f"  WARN image {key!r}: {exc}", file=sys.stderr)
            return None
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.path_for(key, value)
        path.write_bytes(data)
        self.seen[key] = path
        self.saved += 1
        return path


def rewrite_markdown(page_md: str, mapping: dict[str, str], sink: ImageSink,
                     base: Path | None = None) -> str:
    def sub(m: re.Match) -> str:
        src = m.group(1)
        local = sink.seen.get(src)
        if local is None:
            local = sink.save(src, mapping[src])
        if local is None:
            return m.group(0)
        if base is not None:
            try:  # reference images relative to the .md for portability
                return m.group(0).replace(src, Path(os.path.relpath(local, base)).as_posix())
            except ValueError:  # different drives on Windows
                pass
        return m.group(0).replace(src, local.as_posix())

    return IMG_TAG.sub(sub, page_md) if mapping else page_md


def unique_target(path: Path, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def ocr_page_text(page) -> str:
    pr = page.pruned_result
    texts: list | None = None
    if isinstance(pr, dict):
        texts = pr.get("rec_texts")
        if texts is None:
            texts = next((v["rec_texts"] for v in pr.values() if isinstance(v, dict) and "rec_texts" in v), None)
    elif isinstance(pr, list):
        texts = [t for item in pr if isinstance(item, dict) for t in item.get("rec_texts", [])] or None
    return "\n".join(map(str, texts)) if texts else ""


# --------------------------------------------------------------------------- tasks
def run_doc(client, args, src: str) -> str:
    options = PaddleOCRVLOptions(
        use_doc_orientation_classify=args.orient or None,
        use_doc_unwarping=args.unwarp or None,
    )
    result = client.parse_document(
        model=args.model, file_path=src if not is_url(src) else None,
        file_url=src if is_url(src) else None,
        options=options, page_ranges=args.pages,
    )
    if not result.pages:
        return f"SKIP {src}: no content detected"
    first = Path(src) if not is_url(src) else None
    parent = args.out or (first.parent if first else Path.cwd())
    stem = first.stem if first else Path(urlparse(src).path).stem or "download"
    md_path = unique_target(parent / f"{stem}.md", args.overwrite)
    sink = ImageSink(parent / f"{md_path.stem}_images")

    parts: list[str] = []
    for i, page in enumerate(result.pages, 1):
        md = rewrite_markdown(page.markdown_text, page.markdown_images, sink, base=parent)
        if args.page_markers and len(result.pages) > 1:
            md = f"<!-- Page {i} -->\n\n{md.strip()}"
        parts.append(md.strip())
    md_path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    imgs = f" +{sink.saved} images" if sink.saved else ""
    return f"OK   {Path(src).name}: {len(result.pages)}p -> {md_path}{imgs}"


def run_ocr(client, args, src: str) -> str:
    options = OCROptions(
        use_doc_orientation_classify=args.orient or None,
        use_doc_unwarping=args.unwarp or None,
    )
    result = client.ocr(
        model=args.model, file_path=src if not is_url(src) else None,
        file_url=src if is_url(src) else None,
        options=options, page_ranges=args.pages,
    )
    chunks = [ocr_page_text(p) for p in result.pages]
    if not any(chunks):
        return f"SKIP {src}: no text detected"
    first = Path(src) if not is_url(src) else None
    parent = args.out or (first.parent if first else Path.cwd())
    stem = first.stem if first else Path(urlparse(src).path).stem or "download"
    out = unique_target(parent / f"{stem}.txt", args.overwrite)
    if args.page_markers:
        parts = [f"{'-' * 40} Page {i} {'-' * 40}\n\n{c}" for i, c in enumerate(chunks, 1) if c]
        body = "\n\n".join(parts)
    else:
        body = "\n\n".join(chunks)
    out.write_text(body + "\n", encoding="utf-8")
    return f"OK   {Path(src).name}: {len(result.pages)}p -> {out}"


def main() -> int:
    p = argparse.ArgumentParser(description="PaddleOCR (AI Studio hosted) -> Markdown/images or text, saved next to the source file.")
    p.add_argument("inputs", nargs="+", help="absolute file path(s) or http(s) URL(s)")
    p.add_argument("--task", choices=["doc", "ocr"], default="doc",
                   help="doc = full document parsing -> .md + images (default); ocr = plain text -> .txt")
    p.add_argument("--model", default=None,
                   help="doc: PaddleOCR-VL | PaddleOCR-VL-1.5 | PaddleOCR-VL-1.6 (default); ocr: PP-OCRv5 | PP-OCRv6 (default)")
    p.add_argument("--out", type=Path, default=None, help="output dir (default: each input's own directory)")
    p.add_argument("--pages", default=None, help='page ranges for PDFs, e.g. "1-3,7"')
    p.add_argument("--orient", action="store_true", help="enable document orientation classify (skewed/phone photos)")
    p.add_argument("--unwarp", action="store_true", help="enable document unwarping (curved/folded pages)")
    p.add_argument("--overwrite", action="store_true", help="overwrite existing outputs instead of suffixing _1")
    p.add_argument("--no-page-markers", dest="page_markers", action="store_false", help="omit per-page separators")
    p.add_argument("--request-timeout", type=float, default=300.0)
    p.add_argument("--poll-timeout", type=float, default=600.0)
    args = p.parse_args()

    if not args.model:
        args.model = "PaddleOCR-VL-1.6" if args.task == "doc" else "PP-OCRv6"

    for src in args.inputs:
        if not is_url(src) and not Path(src).expanduser().is_absolute():
            print(f"FAIL {src}: relative paths are not supported (use an absolute path)", file=sys.stderr)
            return 1

    token = resolve_token()
    client = PaddleOCRClient(token=token,
                             request_timeout=args.request_timeout,
                             poll_timeout=args.poll_timeout)
    task = run_doc if args.task == "doc" else run_ocr
    failures = 0
    try:
        for src in args.inputs:
            path = str(Path(src).expanduser().resolve()) if not is_url(src) else src
            try:
                print(task(client, args, path), flush=True)
            except Exception as exc:  # noqa: BLE001 - one bad file must not kill the batch
                failures += 1
                print(f"FAIL {src}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    finally:
        client.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
