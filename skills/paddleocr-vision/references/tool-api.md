# PaddleOCR Vision — API 参考

来源：`paddleocr-mcp`（PyPI, ≥3.7）与 `paddleocr._api_client` 官方源码，安装于 uv 隔离环境。

## 1. 两个 MCP 服务器（`mcp_config.json`）

| server | 模型 (`PADDLEOCR_MCP_MODEL`) | 暴露工具 | 用途 |
|---|---|---|---|
| `paddleocr-vl` | `PaddleOCR-VL-1.6` | `paddleocr_vl` | 文档解析 → Markdown（文字/表格/公式/版面） |
| `paddleocr-ocr` | `PP-OCRv6`（不可用则 `PP-OCRv5`） | `ocr` | 快速纯文字识别 |

共同环境变量：
- `PADDLEOCR_MCP_PPOCR_SOURCE=aistudio`
- `PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN=<YOUR_AISTUDIO_ACCESS_TOKEN>`（Token 获取：https://aistudio.baidu.com/account/accessToken）

## 2. MCP 工具入参（两个工具同构）

| 参数 | 类型 | 说明 |
|---|---|---|
| `input_data` | str | **绝对路径**（支持 `~`）、http(s) URL、base64 或 data URL（仅 image/pdf） |
| `output_mode` | `"simple"` \| `"detailed"` | detailed 额外返回 JSON（含 `Pages: N`） |
| `file_type` | `"image"` \| `"pdf"` | HTTP 托管端无法从输入推断类型时必填 |
| `return_images` | bool，默认 True | False 时 Markdown 中 `<img>` 保留为占位符、不返回 base64 |
| `runtime_params` | JSON object | 见 §3 |

返回值：`TextContent`（Markdown 片段）与 `ImageContent`（base64，按原文位置穿插）的列表；
`return_images=false` 或无图时为单个 TextContent。

## 3. runtime_params（VL 与 OCR 任务同款，默认全 False）

- `use_doc_orientation_classify` — 歪斜/手机拍摄件开启
- `use_doc_unwarping` — 弯曲、褶皱页开启

## 4. 脚本 `scripts/ocr_to_files.py` 完整参数

```text
inputs...                绝对路径或 http(s) URL，可多个（批量，逐个容错）
--task doc|ocr           doc: → <stem>.md + <stem>_images/（默认）
                         ocr: → <stem>.txt（纯文字，rec_texts 按页拼接）
--model                  doc 默认 PaddleOCR-VL-1.6；可选 PaddleOCR-VL / -1.5
                         ocr 默认 PP-OCRv6；可选 PP-OCRv5
--out DIR                输出目录（默认：每个输入各自的所在目录）
--pages "1-3,7"          透传给 API 的 page_ranges（大 PDF 分段）
--orient / --unwarp      对应 §3 两个开关
--overwrite              目标已存在时覆盖（默认自动加后缀 _1、_2…）
--no-page-markers        多页文档默认加 <!-- Page N --> 分隔，此开关关闭
--request-timeout S      单次 HTTP 请求超时（默认 300）
--poll-timeout S         任务轮询总超时（默认 600，大文档调大）
```

实现要点：走 `paddleocr._api_client.client.PaddleOCRClient`（官方同步客户端，
submit → poll → fetch），与 MCP 的 aistudio provider 完全同源；图片写入兼容
base64 / data URL / http URL 三种返回形态；Markdown 中的 `<img src>` 改写为
指向 `<stem>_images/` 的相对引用。

## 5. 额度与纪律

AI Studio 官方免费 API：每日 ~20,000 页文档解析，MCP 与脚本共享同一 Token 配额。
超长文档分段使用 `--pages`。
Token 是敏感凭据，严格存储于本地配置文件或本地环境变量，切勿外传或推入 Git 仓库。
