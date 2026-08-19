# ColorFlow Web 部署说明

## 系统要求

| 项 | 要求 |
|---|---|
| Python | **3.11+**（推荐 3.11，已用 3.11.15 验证） |
| 操作系统 | Windows / Linux / macOS |
| 内存 | ≥ 1GB（rembg 抠图推理需要） |
| 网络 | 首次安装依赖需要联网（建议国内使用清华镜像） |

## 安装（首次部署）

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 安装依赖（国内用清华镜像加速）
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# Linux/macOS: .venv/bin/python -m pip install -r requirements.txt

# 3. （可选）验证模型
#    models\silueta.onnx 已随包附带，启动脚本会自动设置 U2NET_HOME
```

## 启动

### Windows
双击 **`start.bat`**（会自动检测 venv 并设置模型目录）。

### 手动启动
```bash
.venv\Scripts\python.exe app.py
# 或 Linux/macOS: .venv/bin/python app.py
```

访问 **http://127.0.0.1:5000**

## 功能说明

| 功能 | 说明 |
|---|---|
| 位图抠图 | rembg（silueta 模型），输出透明 PNG |
| 矢量描图 | VTracer 位图转 SVG，支持忽略白色输出透明 SVG |
| Pantone 查色 | 色号 → CMYK/HEX/RGB |
| 色彩匹配 | HEX → 最近 Pantone 色（ΔE） |

## 模型说明

- 抠图模型 `models\silueta.onnx`（42MB）已包含在包内
- 若删除该文件，首次抠图会自动尝试从 GitHub 下载（国内可能很慢），可用以下镜像手动下载：
  ```
  https://gh.ddlc.top/https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx
  ```
- 模型缓存目录由环境变量 `U2NET_HOME` 控制（默认 `%USERPROFILE%\.u2net`）

## 可选环境变量

| 变量 | 作用 |
|---|---|
| `COLORFLOW_API_KEY` | 设置后启用 `/api/*` 接口鉴权 |
| `PORT` | 自定义端口（默认 5000） |
| `FLASK_DEBUG` | 是否开启 Debug 模式（生产不要开） |

## 生产部署提示

Flask 内置服务器仅适合本地/内网使用。生产环境建议：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
（Windows 上可用 waitress 替代 gunicorn）
