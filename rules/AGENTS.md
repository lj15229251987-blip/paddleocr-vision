# 文档读取与 OCR 优先准则 (OCR-First over Token Waste)

## 核心第一性原理：Token 比 OCR 贵
- 严禁将 PDF 文件（无论文字版还是扫描版）或无法直接阅读的文件直接塞入大模型对话上下文（直接读取整页 PDF 会将整页转为高分辨率图片或产生海量冗余 Token，成本极高）。
- 百度 AI Studio 托管 PaddleOCR 提供充足免费额度（~20,000 页/天），必须充分利用免费 OCR 工具降低 Token 消耗。

## 行为执行铁律
1. **所有 PDF 文件与非纯文本格式**：
   - 一律**优先执行离线脚本 OCR 落盘**：
     ```bash
     uv run --python 3.12 --with paddleocr-mcp --no-project python "<paddleocr-vision>/scripts/ocr_to_files.py" "<pdf_path>"
     ```
   - 落盘产物默认保存在原文档同目录下：`<stem>.md`（多图时配 `<stem>_images/`）。
   - 落盘完成后，通过按需读取、`grep` 或查找关键字的方式阅读 `<stem>.md`，严禁无差别全量加载数百页文档进入上下文。
2. **纯文本类文件（.txt / .md / .c / .h / .py / .json / .csv）**：
   - 保持常规代码/文本读取方式即可。
3. **图片文件**：
   - 提取文字或文档内容：使用 PaddleOCR 脚本或 MCP 工具；
   - 纯视觉分析（硬件实物走线、器件外观形态）：使用原生图片查看。
4. **大文件分段纪律**：
   - 超过 30 页的 PDF 文档必须使用 `--pages` 分段运行（如 `--pages "1-10"`）。
