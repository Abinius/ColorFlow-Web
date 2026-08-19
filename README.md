# ColorFlow Web

> AI 位图抠图 + 矢量描图 + Pantone 色彩管理 — 一个页面搞定从位图到透明 PNG / SVG / 印刷落地

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 定位

ColorFlow Web 是 **ColorFlow 矢量描图 SDK** 和 **Pantone 色彩管理** 的 Web 前端界面，开源可免费部署。将 AI 位图抠图、矢量描图、Pantone 色号匹配、Delta E 色彩偏差计算聚合在一个页面中。

界面采用 **Figma DESIGN.md 设计规范**（黑白编辑风 + 巨型 pastel 色块 + 药丸按钮），布局为 **DeepSeek Harness 式左栏导航 + 内容工作区**双栏结构，移动端自动折叠为抽屉式菜单。

## 功能

| 功能 | 说明 |
|------|------|
| **位图抠图** | 上传位图，rembg（silueta 模型）AI 移除背景，输出**透明 PNG**，棋盘格预览 |
| **矢量描图** | 上传位图（PNG/JPG/WebP/BMP），VTracer 转 SVG，预览 + 下载 |
| **忽略白色** | 描图后自动去除白色路径，输出透明背景 SVG（容差可调） |
| **Pantone 查色** | 输入 Pantone 色号，一键获取 HEX / CMYK / RGB 值 |
| **色彩匹配** | 输入 HEX，自动匹配最近的 5 个 Pantone 色 + ΔE 色彩偏差 |
| **一键流水线** | 描图后自动提取主色 → 逐一匹配 Pantone |
| **AI Agent 接入** | 内置 MCP Server，Claude Code 等 Agent 可直接调用全部能力 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML + CSS + JS（零框架依赖）|
| 后端 | Flask + Python 3.11+ |
| 抠图引擎 | [rembg](https://github.com/danielgatis/rembg)（silueta ONNX 模型，onnxruntime CPU 推理）|
| 描图引擎 | [VTracer](https://github.com/visioncortex/vtracer) (Rust) |
| 色彩数据库 | [mcp-print](https://github.com/kcgdz/mcp-print) (2415 Pantone 色) |
| 矢量输出 | [ColorFlow SDK](https://github.com/Abinius/ColorFlow) |

## 快速启动

### 前提

- **Python 3.11+**
- 国内网络建议使用清华镜像加速依赖安装

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 安装依赖（国内镜像）
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 注意：`colorflow-sdk` 未发布到 PyPI，requirements.txt 已内置 `git+` 引用，会自动从 GitHub 安装。若网络受限，可本地安装：`pip install -e /path/to/ColorFlow`。

### 运行

```bash
# Windows 一键启动
start.bat

# 或手动
.venv\Scripts\python.exe app.py
# → http://localhost:5000
```

### 抠图模型

- 抠图模型 `models/silueta.onnx`（42MB）已随仓库附带，启动时自动设置 `U2NET_HOME` 指向包内目录，**无需联网下载**。
- 若模型缺失，首次抠图会尝试从 GitHub 下载（国内可能很慢），可用镜像：
  ```
  https://gh.ddlc.top/https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx
  ```

### 生产部署

```bash
# 生产环境务必设置 API Key（设置后 /api/* 需要 x-api-key 头，否则开放）
export COLORFLOW_API_KEY="your-secret-key"
export FLASK_DEBUG=false
export PORT=5000
python3 app.py
```

或使用 Gunicorn：

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

详细部署说明见 [DEPLOY.md](DEPLOY.md)。

## AI Agent 接入（MCP Server）

内置 MCP Server，让 Claude Code / Cursor 等 Agent 直接调用描图、抠图、Pantone 匹配、报价能力。

```bash
pip install fastmcp
mcp run mcp_server.py
```

接入 Claude Code（`~/.claude.json` 或项目 `.mcp.json`）：

```json
{
  "mcpServers": {
    "colorflow": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

可用工具：

| Tool | 说明 |
|------|------|
| `trace_image` | 位图 → SVG，返回文件路径 |
| `match_pantone` | HEX → 最近 5 个 Pantone 色 + ΔE |
| `quote_print` | 印刷全链路报价（后端保留，前端已下线）|
| `export_print` | 位图 → 生产印刷级 CMYK PDF（出血 + 物理尺寸）|
| `trace_and_match` | 一键流水线：描图 → 主色 → Pantone 匹配 |

```bash
# Agent 可直接说：
# 「把 D:/img.png 描成矢量，提取主色，匹配 Pantone」
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/cutout` | 位图抠图 → 透明 PNG（base64）|
| `POST` | `/api/trace` | 位图 → SVG（`mode=cutout` 时走抠图+描图）|
| `POST` | `/api/trace/colors` | 描图 + 主色提取 + Pantone 匹配（一键流水线）|
| `POST` | `/api/pantone/match` | HEX → Pantone 最近匹配 + ΔE |
| `GET` | `/api/pantone/lookup?name=` | Pantone 色号精确查询 |
| `GET` | `/api/pantone/colors?page=&limit=&search=` | Pantone 颜色列表（分页）|
| `POST` | `/api/cost/quote` | 印刷报价计算（前端已下线，API 保留）|
| `POST` | `/api/print/export` | 位图 → 印刷级 CMYK PDF 下载 |

### 描图请求参数（multipart/form-data）

| 参数 | 说明 | 默认 |
|------|------|------|
| `image` | 图片文件（PNG/JPG/WebP/BMP，≤10MB）| 必填 |
| `mode` | `color` / `grey` / `human` / `cutout` | `color` |
| `filter_speckle` | 斑点过滤（1-100）| 4 |
| `path_precision` | 路径精度（1-16）| 7 |
| `ignore_white` | `1` 时去除白色路径输出透明 SVG | `0` |

### 示例

```bash
# 抠图 → 透明 PNG
curl -X POST http://localhost:5000/api/cutout \
  -F "image=@photo.jpg"

# 色彩匹配
curl -X POST http://localhost:5000/api/pantone/match \
  -H "Content-Type: application/json" \
  -d '{"hex_color": "#DA291C"}'
```

## 错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 参数错误 / 缺少必要字段 / 非法 JSON |
| 415 | 不支持的图片类型或未带 JSON Content-Type |
| 500 | 服务端执行失败 |

## 设计规范

界面遵循 [Figma DESIGN.md 设计语言](https://github.com/Abinius/awesome-design-md)（`awesome-design-md/design-md/figma/DESIGN.md`）：

- **黑白编辑风**：纯白画布 + 纯黑墨色，所有 CTA 为药丸形（pill），图标按钮为圆形
- **pastel 色块**：lime / lilac / cream / mint / pink 等大色块点缀（logo mark、强调按钮）
- **字体**：Inter 变量字体（权重 320–700 细腻分级）+ JetBrains Mono（caption/eyebrow）
- **布局**：DeepSeek Harness 式左栏（LOGO + 工具导航 + footer）+ 右侧内容工作区，移动端抽屉折叠

## 架构

```
colorflow-web/
├── app.py              # Flask 入口，所有 API 路由
├── mcp_server.py       # MCP Server（Agent 接入）
├── templates/
│   └── index.html     # 单页（位图抠图 / 矢量描图 / Pantone 查色 / 色彩匹配）
├── static/
│   ├── style.css      # Figma DESIGN.md 黑白编辑风样式
│   └── app.js         # 前端交互逻辑
├── models/
│   └── silueta.onnx   # 抠图模型（42MB，随包附带）
├── tests/
│   ├── test_app.py    # API 集成测试
│   └── test_mcp.py    # MCP Server 冒烟测试
├── start.bat          # Windows 一键启动
├── DEPLOY.md          # 部署说明
└── requirements.txt   # 依赖清单
```

## 测试

```bash
pip install pytest
python -m pytest tests/ -q     # 41 个用例
```

## 相关项目

| 项目 | 说明 |
|------|------|
| [ColorFlow SDK](https://github.com/Abinius/ColorFlow) | AI Agent 矢量描图 SDK（Python/CLI/API）|
| [mcp-print](https://github.com/kcgdz/mcp-print) | Pantone + CMYK + Delta E + 印刷报价（2415 色）|
| [vtracer](https://github.com/visioncortex/vtracer) | Rust 矢量描图引擎 |
| [rembg](https://github.com/danielgatis/rembg) | AI 背景移除（silueta/u2net 模型）|

## License

MIT © AbinCheungCom
