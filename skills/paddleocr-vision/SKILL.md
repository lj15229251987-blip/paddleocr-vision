---
name: paddleocr-vision
description: >
  Read documents and images faithfully with Baidu PaddleOCR (SOTA OCR VLM,
  hosted, ~20k free pages/day). Use whenever the user asks to OCR, extract,
  transcribe or convert documents to Markdown — scanned PDFs, image-only PDFs,
  schematics, chip datasheets, photos of pages, handwriting, complex tables,
  formulas, stamps, multilingual text, or any PDF whose Read result comes back empty/garbled.
  Trigger words: OCR, 扫描件, 识别文字, 图片转文字, 转 Markdown, 提取表格, 提取公式,
  原理图文字, 数据手册解析, 文档解析, read this scan, extract text.
  NOTE: For ordinary text files (.c, .h, .py, .txt, .md, .csv, .json), read directly.
  For ALL PDF files and unreadable files, ALWAYS run offline OCR to disk first.
---

# PaddleOCR Vision — 文档视觉与高精度 OCR

> 本插件由百度飞桨 PaddleOCR 官方提供 SOTA 文档级图文理解与 OCR 能力（~20,000 免费页/天）。

你有三项能力，选对路径是本技能的核心：

| 能力 | 载体 | 特点 |
|---|---|---|
| `scripts/ocr_to_files.py` | 直连官方同步客户端 | **产物直接落盘、零上下文消耗**，支持批量、页范围、URL（首选） |
| `paddleocr_vl` 工具 | MCP server `paddleocr-vl`（PaddleOCR-VL-1.6） | 整页解析成 Markdown（文字+表格+公式+版面），**结果经过对话上下文** |
| `ocr` 工具 | MCP server `paddleocr-ocr`（PP-OCRv6） | 快速纯文字提取，轻量 |

完整参数与错误码见同目录 `references/tool-api.md`。

---

## 1. 核心第一性原理与决策矩阵

**总原则：LLM Token 远比免费 OCR 额度贵——能用免费 OCR 换 Token 就坚决用 OCR。**

1. **一切 PDF 文件（无论扫描版还是电子版）→ 一律先走脚本 OCR**：
   - 原生大模型读 PDF 会将每一页渲染为高分辨率图片载入上下文，或产生数万 Token 消耗，极为昂贵；
   - OCR 后的 Markdown 是结构化纯文本，且落盘脚本运行在外部子进程中，**产生 0 对话 Token 消耗**；
   - 落盘后，回答具体问题时优先使用搜索或局部定位，切忌把几十万字整本大文档一次性全读进上下文。
2. **纯文本类文件（txt/md/c/h/py/json/csv/v/sv）→ 直接读**（OCR 无收益且增加耗时）。
3. **图片文件**：
   - 提取文字/转 Markdown/提取表格 → 走 PaddleOCR 脚本或 MCP 工具；
   - 纯视觉理解（硬件走线形态、三维结构外观）→ 原生看图。
4. **读不了的文件（乱码、加密、格式不支持）→ 优先转 OCR 脚本**。
5. **MCP 工具（`paddleocr_vl` / `ocr`）**：
   - 仅在用户明确要求交互式查看或单步实时验证时使用；由于返回内容进上下文，默认被脚本落盘路径取代。

---

## 2. 路径 A：脚本离线落盘（首选，大文档/批量/数据手册）

产物**默认保存在原文档同目录**：`<stem>.md` + `<stem>_images/`（图片引用已自动改写为相对路径）。如果是纯文字提取任务（`--task ocr`）则输出 `<stem>.txt`。

### 命令模板
```bash
uv run --python 3.12 --with paddleocr-mcp --no-project python \
  "<paddleocr-vision>/scripts/ocr_to_files.py" \
  "<文档绝对路径.pdf>" [options]
```

### 常用参数速查
- `--task doc`（默认）：完整版面分析，生成 Markdown 表格（HTML `<table>`）与公式（`$...$`）并抽取出图片到 `<stem>_images/`；
- `--task ocr`：极速纯文字识别，输出 `<stem>.txt`；
- `--pages "1-3,7"`：页码范围筛选（**重要**：超过 30 页的 PDF 请务必分段，防止服务端超时）；
- `--orient`：自动矫正手机拍摄件/歪斜页面；
- `--unwarp`：自动展开弯曲或折痕书页；
- `--out <DIR>`：指定自定义输出目录（默认输出在文档自身同目录下）；
- `--overwrite`：覆盖已有输出（默认自动重命名为 `_1.md`，防止覆盖既有成果）；
- 批量处理：输入多个绝对路径，脚本逐一容错处理，单个失败不中断整批。

---

## 3. 路径 B：MCP 交互式工具（亲眼查看结果）

调用 `paddleocr_vl`（或轻量的 `ocr`），入参必须为**绝对路径**：

- `return_images: false`：当只需要文字与表格结构时设为 `false`，极大节省 Token；
- `output_mode: "detailed"`：返回 JSON 格式的元数据（包含总页数等）；
- `runtime_params: {"use_doc_orientation_classify": true, "use_doc_unwarping": true}`：用于歪斜或拍摄文档。

---

## 4. 自检与排障

怀疑配置或网络连通性时，运行自检套件：
```bash
uv run --python 3.12 --with paddleocr-mcp --no-project python \
  "<paddleocr-vision>/scripts/mcp_selftest.py"
```
预期：自动测试 `paddleocr-vl` 与 `paddleocr-ocr` 两大服务，打印 `ALL MCP TESTS PASSED SUCCESSFUL`。
