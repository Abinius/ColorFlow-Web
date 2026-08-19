# ColorFlow Web

> AI 位图抠图 + 矢量描图 + Pantone 色彩管理 — 一个页面搞定从位图到透明 PNG / SVG / 印刷落地

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 定位

ColorFlow Web 是 **ColorFlow 矢量描图 SDK** 和 **Pantone 色彩管理** 的 Web 前端界面，开源可免费部署。将 AI 位图抠图、矢量描图、Pantone 色号匹配、Delta E 色彩偏差计算聚合在一个页面中。

界面采用 **Figma DESIGN.md 设计规范**（黑白编辑风 + 巨型 pastel 色块 + 药丸按钮），布局为 **DeepSeek Harness 式左栏导航 + 内容工作区**双栏结构，移动端自动折叠为抽屉式菜单。

## 功能

| 功能 | 说明 |
|------|------|
| **位图抠图** | 上传位图，rembg AI 移除背景，8 模型可选 + Alpha Matting 边缘细化，输出**透明 PNG** |
| **矢量描图** | 上传位图（PNG/JPG/WebP/BMP），VTracer 转 SVG，10 个精度参数可调 |
| **忽略白色** | 描图后自动去除白色路径，输出透明背景 SVG（容差可调） |
| **Pantone 查色** | 输入 Pantone 色号，一键获取 HEX / CMYK / RGB 值 |
| **色彩匹配** | 输入 HEX，自动匹配最近的 5 个 Pantone 色 + ΔE 色彩偏差 |
| **一键流水线** | 描图后自动提取主色 → 逐一匹配 Pantone |
| **印刷 PDF 导出** | 位图 → 生产印刷级 CMYK PDF（含出血 + 物理尺寸） |
| **Pantone 色卡导出** | 色号查询详情一键导出色卡 PDF；匹配结果导出报告 PDF（CMYK 印刷级）|
| **API Key 管理** | 设置页一键生成 / 撤销 Key，Web API 与 MCP 共用 |
| **AI Agent 接入** | 内置 MCP Server（10 工具），Claude Code / Cursor 可直接调用 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML + CSS + JS（零框架依赖）|
| 后端 | Flask + Python 3.11+ |
| 抠图引擎 | [rembg](https://github.com/danielgatis/rembg)（silueta ONNX 模型，onnxruntime CPU 推理）|
| 描图引擎 | [VTracer](https://github.com/visioncortex/vtracer) (Rust) |
| 色彩数据库 | [mcp-print](https://github.com/kcgdz/mcp-print) (2415 Pantone 色) |
| 矢量输出 | [ColorFlow SDK](https://github.com/Abinius/ColorFlow) |
| MCP Server | [FastMCP](https://github.com/jlowin/fastmcp) — Agent 标准接入协议 |
| Key 存储 | JSON 文件（`~/.colorflow/keys.json`，权限 0600）|

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

## API Key 管理

### 生成 Key（推荐）

启动服务后打开 **设置页**（左栏底部齿轮图标）→ 「生成新 Key」按钮 → 输入名称 → Key 明文仅显示一次 → 自动填充到 MCP 配置。

- Key 存储在 `~/.colorflow/keys.json`（文件权限 0600）
- 支持多个 Key，每个可命名 / 撤销
- 撤销后即时生效，所有请求立即被拒
- 首次无 Key 时全部开放（本地开发模式）

### 环境变量（向后兼容）

```bash
# 传统方式：启动前设置环境变量（仍然有效，会自动 bootstrap 进 KeyStore）
export COLORFLOW_API_KEY="cf_sk_xxx"
```

### 生产部署

```bash
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

内置 MCP Server，让 Claude Code / Cursor 等 Agent 直接调用全部能力。

### 快速接入

1. 启动 ColorFlow Web 服务
2. 打开设置页 → 生成 API Key → 复制 `.mcp.json` 配置（Key 已自动填充）
3. 粘贴到 Claude Code / Cursor 的配置文件

```json
{
  "mcpServers": {
    "colorflow": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {
        "COLORFLOW_API_KEY": "cf_sk_xxx"
      }
    }
  }
}
```

### 可用工具（10 个）

| Tool | 说明 | 关键参数 |
|------|------|---------|
| `trace_image` | 位图 → SVG 矢量图 | mode, colormode, hierarchical, 8 个精度参数 |
| `cutout` | AI 抠图 → 透明 PNG | model（8 选）, alpha_matting（3 阈值）|
| `cutout_then_trace` | 抠图 + 描图一键串联 | 抠图参数 + 描图参数全量 |
| `trace_and_match` | 描图 → 主色 → Pantone 匹配 | 8 个精度参数 |
| `match_pantone` | HEX → 最近 5 个 Pantone + ΔE | hex_color |
| `pantone_lookup` | 按色号精确查询 Pantone | name（如 485C）|
| `pantone_colors` | Pantone 色库分页 + 搜索 | page, limit, search |
| `quote_print` | 印刷全链路报价 | width, height, qty, colors, gsm, method |
| `export_print` | 位图 → 印刷级 CMYK PDF | width_mm, height_mm, bleed_mm, mode |
| `export_pantone_pdf` | 色卡 / 匹配报告 PDF | export_type（swatch / report）, 颜色数据 |

### Agent 调用示例

```
用户: 「把 D:/img.png 描成矢量，提取主色，匹配 Pantone」
Agent: 调用 trace_and_match("D:/img.png")
  → SVG 文件路径 + 调色板（主色 + Pantone 匹配 + ΔE）

用户: 「帮我把这张照片背景抠掉」
Agent: 调用 cutout("D:/photo.jpg", model="silueta", alpha_matting=True)
  → 透明 PNG 文件路径

用户: 「查询 Pantone 485C 的 CMYK 值」
Agent: 调用 pantone_lookup("485C")
  → {name, hex, c, m, y, k, rgb}

用户: 「把 485C 的色值导出成色卡 PDF」
Agent: 调用 export_pantone_pdf(export_type="swatch", name="485 C",
         hex_color="#DA291C", cmyk=[0,85,95,5], rgb=[218,41,28])
  → {success, pdf_path}
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
| `POST` | `/api/cost/quote` | 印刷报价计算 |
| `POST` | `/api/print/export` | 位图 → 印刷级 CMYK PDF 下载 |
| `POST` | `/api/pantone/export` | 色卡 / 匹配报告 PDF（CMYK）|
| `POST` | `/api/keys/generate` | 生成新 API Key |
| `GET` | `/api/keys` | 列出所有 Key（脱敏）|
| `DELETE` | `/api/keys/<key_id>` | 撤销指定 Key |

### 描图请求参数（multipart/form-data）

| 参数 | 说明 | 默认 |
|------|------|------|
| `image` | 图片文件（PNG/JPG/WebP/BMP，≤10MB）| 必填 |
| `mode` | `color` / `grey` / `human` / `cutout` | `color` |
| `colormode` | `rgb8` / `rgb16` / `mono` / `grey` / `grey16` | `rgb8` |
| `hierarchical` | `stacked` / `flat` | `stacked` |
| `filter_speckle` | 斑点过滤（1-100）| 4 |
| `color_precision` | 颜色精度（1-16）| 6 |
| `layer_difference` | 图层距离（1-256）| 64 |
| `corner_threshold` | 角点阈值（1-180）| 60 |
| `length_threshold` | 路径最短长度（0.1-100）| 2.0 |
| `path_precision` | 路径精度（1-16）| 7 |
| `ignore_white` | `1` 时去除白色路径输出透明 SVG | `0` |

### 抠图请求参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `model` | silueta / u2net / u2net_human_seg / u2netp / dis_anime / dis_general_use / withoutbg / bria-rmbg | `silueta` |
| `alpha_matting` | `1` 启用边缘细化 | `0` |
| `alpha_matting_foreground_threshold` | 前景阈值（10-255）| 240 |
| `alpha_matting_background_threshold` | 背景阈值（0-245）| 10 |
| `alpha_matting_erode_size` | 腐蚀尺寸（1-20）| 10 |
| `decontaminate` | `1` 清除边缘色晕 | `0` |
| `post_process_mask` | `1` 二值掩码去噪 | `0` |

### 示例

```bash
# 抠图 → 透明 PNG
curl -X POST http://localhost:5000/api/cutout \
  -F "image=@photo.jpg" \
  -F "model=silueta" \
  -F "alpha_matting=1"

# 矢量描图
curl -X POST http://localhost:5000/api/trace \
  -F "image=@logo.png" \
  -F "mode=color" \
  -F "colormode=mono" \
  -F "path_precision=10"

# 色彩匹配
curl -X POST http://localhost:5000/api/pantone/match \
  -H "Content-Type: application/json" \
  -d '{"hex_color": "#DA291C"}'

# 生成 API Key
curl -X POST http://localhost:5000/api/keys/generate \
  -H "Content-Type: application/json" \
  -d '{"name": "我的 Agent"}'

# 导出色卡 PDF
curl -X POST http://localhost:5000/api/pantone/export \
  -H "Content-Type: application/json" \
  -d '{"type": "swatch", "name": "485 C", "hex": "#DA291C", "cmyk": [0,85,95,5], "rgb": [218,41,28]}'
```

## 错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 参数错误 / 缺少必要字段 / 非法 JSON |
| 401 | API Key 缺失或无效 |
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
├── app.py               # Flask 入口，所有 API 路由 + Key 管理端点
├── colorflow_keys.py    # KeyStore：API Key 生成 / 校验 / 撤销
├── mcp_server.py        # MCP Server（10 工具 + Key 认证）
├── templates/
│   └── index.html      # 单页（抠图 / 描图 / Pantone / 色彩匹配 + 设置页）
├── static/
│   ├── style.css       # Figma DESIGN.md 样式
│   ├── app.js          # 前端交互 + Key 管理 + MCP 配置
│   └── favicon.*       # 浏览器图标（ico/png/svg/manifest）
├── models/
│   └── silueta.onnx    # 抠图模型（42MB，随包附带）
├── tests/
│   ├── test_app.py     # API 集成测试 + Key 管理测试
│   └── test_mcp.py     # MCP Server 全工具测试
├── start.bat           # Windows 一键启动
├── DEPLOY.md           # 部署说明
└── requirements.txt    # 依赖清单
```

## 测试

```bash
pip install pytest
python -m pytest tests/ -q     # 59 个用例
```

## 相关项目

| 项目 | 说明 |
|------|------|
| [ColorFlow SDK](https://github.com/Abinius/ColorFlow) | AI Agent 矢量描图 SDK（Python/CLI/API）|
| [mcp-print](https://github.com/kcgdz/mcp-print) | Pantone + CMYK + Delta E + 印刷报价（2415 色）|
| [vtracer](https://github.com/visioncortex/vtracer) | Rust 矢量描图引擎 |
| [rembg](https://github.com/danielgatis/rembg) | AI 背景移除（silueta/u2net 模型）|
| [FastMCP](https://github.com/jlowin/fastmcp) | MCP Server 框架 |

## License

MIT © AbinCheungCom
