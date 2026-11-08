# PaddleOCR Vision 部署指南

给任何 coding agent（Antigravity / ZCode / Claude Code / Codex 等）配备"OCR 文档眼睛"的完整流程。

## 架构总览

装完后 agent 获得三个能力：

| 能力 | 载体 | 适用场景 |
|---|---|---|
| `scripts/ocr_to_files.py` 脚本 | 直连同一托管 API 的官方同步客户端 | **交付文件/批量/大文档**：产物直接落盘，零上下文消耗（推荐） |
| `paddleocr_vl` MCP 工具 | 服务器 `paddleocr-vl`（PaddleOCR-VL-1.6） | 交互式解析：扫描件/图片 PDF → Markdown（文字+表格+公式+版面），结果进对话上下文 |
| `ocr` MCP 工具 | 服务器 `paddleocr-ocr`（PP-OCRv6） | 快速纯文字提取 |

两条通道走的是同一个百度 AI Studio 托管服务（免费 ~20,000 页/天，共享额度与 Token）。
完整 API 细节见本目录 `skills/paddleocr-vision/references/tool-api.md`。

---

## 步骤 1：前置条件

```bash
# uv（Python 环境管理器，MCP 与脚本都靠它拉起隔离环境）
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

百度账号 → 打开 https://aistudio.baidu.com/account/accessToken → 创建 Access Token。

---

## 步骤 2：环境预检

```bash
uvx --python 3.12 --from paddleocr-mcp paddleocr_mcp --help
```

成功标志：打印 usage（`PaddleOCR MCP server.`）。
> ⚠️ **不要省略 `--python 3.12`**：uvx 默认会抓系统上最新的 Python（如 3.14），而依赖 pyyaml 6.0.2 在 3.14 没有预编译 wheel，会源码编译失败。

---

## 步骤 3：写 MCP 配置

两个服务器的**通用定义**（任何支持 MCP 的 agent 都用这个结构）：

```json
{
  "paddleocr-vl": {
    "command": "uvx",
    "args": ["--python", "3.12", "--from", "paddleocr-mcp", "paddleocr_mcp"],
    "env": {
      "PADDLEOCR_MCP_MODEL": "PaddleOCR-VL-1.6",
      "PADDLEOCR_MCP_PPOCR_SOURCE": "aistudio",
      "PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN": "<YOUR_AISTUDIO_ACCESS_TOKEN>"
    }
  },
  "paddleocr-ocr": {
    "command": "uvx",
    "args": ["--python", "3.12", "--from", "paddleocr-mcp", "paddleocr_mcp"],
    "env": {
      "PADDLEOCR_MCP_MODEL": "PP-OCRv6",
      "PADDLEOCR_MCP_PPOCR_SOURCE": "aistudio",
      "PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN": "<YOUR_AISTUDIO_ACCESS_TOKEN>"
    }
  }
}
```

放到对应 agent 的配置位置：

| Agent | 配置文件路径 | 配置结构 |
|---|---|---|
| **Antigravity** | `~/.gemini/config/plugins/paddleocr-vision/mcp_config.json` 或 `~/.gemini/config/mcp_config.json` | 顶层 `{"mcpServers": { ... }}` |
| **ZCode** | `~/.zcode/cli/config.json` | 嵌套 `"mcp": { "servers": { ... } }` |
| **Claude Code** | `~/.claude.json` 或运行 `claude mcp add` | 顶层 `{"mcpServers": { ... }}` |
| **Codex** | `~/.codex/config.toml` | `[mcp_servers.<name>]` 段落式 |
| **通用项目级** | `<project>/.mcp.json` | 顶层 `{"mcpServers": { ... }}` |

---

## 步骤 4：验证

```bash
# A. MCP 协议层自检：真实拉起两个服务器、列工具、各调用一次
uv run --python 3.12 --with paddleocr-mcp --no-project python \
  "skills/paddleocr-vision/scripts/mcp_selftest.py" "<图片绝对路径>"
# 预期：paddleocr-vl → ['paddleocr_vl']；paddleocr-ocr → ['ocr']；各返回识别文本，is_error: False

# B. 落盘链路：生成 md + images 于图片同目录
uv run --python 3.12 --with paddleocr-mcp --no-project python \
  "skills/paddleocr-vision/scripts/ocr_to_files.py" "<图片或PDF绝对路径>"
# 预期：打印 "OK xxx.pdf: Np -> ...md"；同目录出现 <stem>.md（+ <stem>_images/）
```

---

## 安全须知

- Token 是个人私密凭证：只存在本地配置或环境变量中，**切勿提交到任何公开仓库或写入项目文件**。
- 若怀疑泄漏，可前往 AI Studio 的 accessToken 页面删除并重新生成。
