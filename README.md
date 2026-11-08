# PaddleOCR Vision — AI Agent 全局文档眼睛与高精度 OCR 插件

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PaddleOCR](https://img.shields.io/badge/PaddleOCR-v3.7+-red.svg)](https://github.com/PaddlePaddle/PaddleOCR)
[![Python](https://img.shields.io/badge/python-3.12-brightgreen.svg)](https://www.python.org/)

面向 AI Coding Agent（Antigravity、Claude Code、Codex、ZCode 等）构建的高保真 OCR 与文档多模态解析插件。集成百度飞桨官方 SOTA 视觉语言模型（PaddleOCR-VL-1.6）与高精度文字识别引擎（PP-OCRv6），依托官方托管 API 提供每日 ~20,000 页的免费文档处理能力。

---

## 🌟 核心理念：Token 比免费 OCR 额度贵

- **解决大模型读文档痛点**：传统 Agent 读取 PDF 时直接将整页转为高分辨率图片载入上下文，不仅吞噬成千上万的高价 Token，还极易丢失深层表格与公式排版。
- **0 上下文消耗就地落盘**：通过离线同步批处理客户端 `ocr_to_files.py`，PDF/扫描件/拍摄件在外部子进程中直接转换为 Markdown + 本地图片切片，**对话上下文开销为 0**。
- **全要素结构化解析**：
  - **表格**：完美转换为多行多列、含合并单元格的 HTML `<table>`；
  - **公式**：自动转译为 KaTeX / LaTeX 行内与块级数学公式（`$...$`）；
  - **版面与图表**：自动将文档插图和电路原理图切片抽取并重写为相对路径引用。

---

## 📂 目录结构

```text
paddleocr-vision/
├── plugin.json                 # 插件元信息与推荐启动指令
├── mcp_config.example.json     # MCP 双服务模板配置
├── mcp_config.json             # MCP 服务配置（默认已脱敏）
├── DEPLOY.md                   # 跨平台 / 多 Agent 详细部署与配置手册
├── LICENSE                     # Apache 2.0 开源协议
├── README.md                   # 插件说明文档
├── rules/
│   └── AGENTS.md               # 插件激活时全局注入的 OCR-First 行为准则
└── skills/
    └── paddleocr-vision/
        ├── SKILL.md            # Agent 技能指令与决策矩阵
        ├── references/
        │   └── tool-api.md     # 官方 API 接口、参数与返回值参考
        └── scripts/
            ├── ocr_to_files.py # 核心落盘批处理转换脚本（直连官方同步客户端）
            └── mcp_selftest.py # MCP 协议与服务可用性自动化验证套件
```

---

## 🚀 快速开始

### 1. 前置依赖安装

本项目通过现代 Python 包管理工具 `uv` 隔离运行（推荐 Python 3.12）：
```bash
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 获取 API Token

前往 [百度飞桨 AI Studio Access Token](https://aistudio.baidu.com/account/accessToken) 免费创建个人访问令牌（每日享有 ~20,000 页免费额度）。

在系统环境变量中配置（或写入各 Agent 的 MCP 配置文件中）：
```bash
# 环境变量方式（推荐）
export PADDLEOCR_MCP_AISTUDIO_ACCESS_TOKEN="<YOUR_TOKEN>"
```

### 3. 一键解析与落盘文档

```bash
uv run --python 3.12 --with paddleocr-mcp --no-project python \
  "skills/paddleocr-vision/scripts/ocr_to_files.py" \
  "/path/to/document.pdf"
```

产物将在源文件同级目录下自动生成：
- `<stem>.md`：结构化 Markdown 文本
- `<stem>_images/`：文档内嵌的图表与图片切片

### 4. 自动化自检

```bash
uv run --python 3.12 --with paddleocr-mcp --no-project python \
  "skills/paddleocr-vision/scripts/mcp_selftest.py"
```

---

## ⚙️ MCP 服务支持

提供标准的 MCP (Model Context Protocol) 双服务配置：

- **`paddleocr-vl`** (PaddleOCR-VL-1.6)：用于需要 Agent 实时查看排版、表格与公式的复杂文档解析；
- **`paddleocr-ocr`** (PP-OCRv6)：毫秒级极速纯文字流提取。

具体多 Agent（Antigravity、Claude Code、Codex、ZCode）集成方式详见 [DEPLOY.md](DEPLOY.md)。

---

## 📄 开源许可

本项目遵循 [Apache-2.0 License](LICENSE)。
