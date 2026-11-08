"""MCP self-test: spawn each configured server, list tools, make real calls.
Usage:
  uv run --python 3.12 --with paddleocr-mcp --no-project python mcp_selftest.py [image-abs-path]
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

# Ensure UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

UVX = shutil.which("uvx") or "uvx"
ARGS = ["--python", "3.12", "--from", "paddleocr-mcp", "paddleocr_mcp"]


def load_config() -> dict:
    candidates = [
        Path(__file__).resolve().parents[2] / "mcp_config.json",
        Path.home() / ".gemini" / "config" / "plugins" / "paddleocr-vision" / "mcp_config.json",
        Path.home() / ".gemini" / "config" / "mcp_config.json",
        Path.home() / ".zcode" / "cli" / "config.json",
        Path.home() / ".claude.json",
    ]
    for c in candidates:
        if c.is_file():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                servers = data.get("mcpServers") or data.get("mcp", {}).get("servers")
                if isinstance(servers, dict) and "paddleocr-vl" in servers:
                    return servers
            except Exception:
                continue
    raise RuntimeError("Could not find paddleocr MCP configuration in any standard path")


SERVERS_CFG = load_config()


def env_for(server_name: str) -> dict:
    e = dict(os.environ)
    srv = SERVERS_CFG.get(server_name, {})
    e.update(srv.get("env", {}))
    return e


def describe(res) -> list[tuple[str, str]]:
    out = []
    for c in res.content:
        if c.type == "text":
            out.append(("TEXT", c.text[:150].replace("\n", " | ")))
        elif c.type == "image":
            out.append(("IMAGE", f"{len(c.data)}b base64, mime={c.mimeType}"))
        else:
            out.append((c.type, ""))
    return out


async def test(server_name: str, tool: str, args: dict | None, label: str):
    print(f"\n=== {label}: {server_name} / {tool} ===", flush=True)
    p = StdioServerParameters(command=UVX, args=ARGS, env=env_for(server_name))
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            print("Discovered tools:", tools, flush=True)
            if tool not in tools:
                print(f"ERROR: Expected tool {tool} not found in {tools}", file=sys.stderr)
                return False
            if args is not None:
                print(f"Calling tool {tool}...", flush=True)
                res = await s.call_tool(tool, args)
                print(f"is_error: {res.is_error}", flush=True)
                for kind, preview in describe(res):
                    print(f"  [{kind}] {preview}", flush=True)
                if res.is_error:
                    return False
    return True


async def main():
    image = sys.argv[1] if len(sys.argv) > 1 else None
    ok1 = await test(
        "paddleocr-vl",
        "paddleocr_vl",
        {"input_data": image, "return_images": False, "output_mode": "detailed"} if image else None,
        "VL tool (PaddleOCR-VL-1.6)",
    )
    ok2 = await test(
        "paddleocr-ocr",
        "ocr",
        {"input_data": image} if image else None,
        "OCR tool (PP-OCRv6)",
    )
    if ok1 and ok2:
        print("\nALL MCP TESTS PASSED SUCCESSFUL", flush=True)
        return 0
    else:
        print("\nMCP SELF-TEST FAILED", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code or 0)
