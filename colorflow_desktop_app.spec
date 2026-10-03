# PyInstaller 打包配置 — ColorFlow Desktop 原生应用
# 用法: .venv\Scripts\pyinstaller.exe colorflow_desktop_app.spec
#
# 说明：BASE_DIR 相对计算（从本 .spec 文件位置推导），保证在任意目录
# 运行或 CI 中都能定位项目源码，避免硬编码绝对路径。
#
# 模型打包策略：只随包 silueta.onnx（42MB，程序默认模型）。旧配置把整个 models/
# 目录塞进 datas，而该目录里还有 u2net_human_seg.onnx（168MB，.gitignore 排除、
# 需手动下载），单文件 exe 会因此白白膨胀 168MB。需要离线人像模型时显式打开：
#     set COLORFLOW_BUNDLE_U2NET=1 && pyinstaller colorflow_desktop_app.spec
# 平时更推荐让用户在运行时下载到用户模型目录（%LOCALAPPDATA%\ColorFlow\models，
# 见 colorflow_desktop_app.py 的 resolve_models_dir），该目录跨版本保留。

import os

# PyInstaller 用 exec() 执行 .spec，其命名空间里**没有** __file__（6.x 提供的是
# SPECPATH）。原来写的 os.path.abspath(__file__) 会让打包在第一步就中断：
#     NameError: name '__file__' is not defined
# SPECPATH 就是本 .spec 所在目录，语义与注释所述完全一致。
HERE = os.path.abspath(SPECPATH)
BASE_DIR = HERE
ENTRY = os.path.join(BASE_DIR, "colorflow_desktop_app.py")

# 固定产物位置：PyInstaller 默认把 build/ 与 dist/ 建在**当前工作目录**下，从仓库外
# 执行会把产物散落到别处（本项目此前就落在 D:\Abin\abincheung\WEB\ 下）。这里把最终
# 输出钉到仓库内，与 .gitignore 里的 build/ dist/ 对齐。
#
# 注意：PyInstaller 在执行本 .spec **之前**就会 makedirs(CONF['distpath'], CONF['workpath'])
# （见 build_main.py 的 "Create DISTPATH and workpath"），所以当工作目录不可写时
# （例如从 C:\ 执行）它在那一步就会失败。该场景必须用命令行参数指定：
#     pyinstaller --distpath <repo>\dist --workpath <repo>\build colorflow_desktop_app.spec
# 推荐直接用 tools/build_desktop.ps1，它已显式传好这两个参数。
from PyInstaller.config import CONF

CONF['distpath'] = os.path.join(BASE_DIR, "dist")
CONF['workpath'] = os.path.join(BASE_DIR, "build")

BUNDLE_U2NET = os.environ.get("COLORFLOW_BUNDLE_U2NET") == "1"
MODEL_FILES = ["silueta.onnx"] + (["u2net_human_seg.onnx"] if BUNDLE_U2NET else [])

# 桌面图标：colorflow.ico 是「深色方块 + 实心白 M」——深色方块保证浅色背景上清楚，实心白 M
# 保证深色背景上可辨认。（若 M 做成透明镂空，深色背景下方块与 M 会一起消失，这就是原缺陷。）
ICON_NAME = "colorflow.ico"

datas = [
    (os.path.join(BASE_DIR, "templates"), "templates"),
    (os.path.join(BASE_DIR, "static"), "static"),
    (os.path.join(BASE_DIR, "assets"), "assets"),     # ComfyUI 工作流模板
    (os.path.join(BASE_DIR, ICON_NAME), "."),         # 窗口图标（frozen 时从 _MEIPASS 读取）
]

# 逐个文件打包（而不是整个 models/ 目录），避免连带塞入未选中的模型与 rembg 缓存目录
_bundled_mb = 0.0
for _name in MODEL_FILES:
    _path = os.path.join(BASE_DIR, "models", _name)
    if os.path.exists(_path):
        _size_mb = os.path.getsize(_path) / (1024 * 1024)
        datas.append((_path, "models"))
        _bundled_mb += _size_mb
        print(f"[spec] 打入模型 models/{_name} ({_size_mb:.1f} MB)")
    else:
        print(f"[spec] 跳过缺失的模型 models/{_name}（请先运行 download_models.py）")
print(f"[spec] 模型合计 {_bundled_mb:.1f} MB；COLORFLOW_BUNDLE_U2NET={BUNDLE_U2NET}")

# 下列包都没有 PyInstaller hook，它们的**非 .py 运行时文件**必须显式收集，否则：
#   webview     -> 缺 WebView2 托管程序集 + WebView2Loader.dll + 注入用 js，创建窗口即失败
#   clr_loader  -> 缺原生 ClrLoader.dll（netfx/coreclr 宿主都靠它）
#   pythonnet   -> 缺 Python.Runtime.dll 及其依赖
#   mcp_print   -> 缺 Pantone 色库数据 data/pantone_colors.json（它是 JSON 数据文件，
#                  PyInstaller 不会自动收），/api/pantone/* 会报 FileNotFoundError
from PyInstaller.utils.hooks import collect_data_files

for _pkg in ("webview", "clr_loader", "pythonnet", "mcp_print"):
    _collected = collect_data_files(_pkg)
    datas += _collected
    print(f"[spec] 收集 {_pkg} 运行时文件 {len(_collected)} 个")

hiddenimports = [
    # 桌面窗口
    "flask", "jinja2", "markupsafe", "werkzeug",
    "webview", "webview.gui", "webview.http", "webview.settings",
    "pythonnet", "clr_loader", "bottle",
    # 图像 / 抠图 / 描图
    "numpy", "PIL", "PIL.Image", "PIL.ImageFilter", "PIL.ImageOps",
    "PIL.ImageEnhance", "PIL.ImageDraw", "PIL.ImageFont",
    "onnxruntime", "onnxruntime.capi",
    "lxml", "svglib", "reportlab", "reportlab.lib", "reportlab.pdfgen",
    "reportlab.graphics",
    # 项目自研模块（本地模块需显式声明，防 PyInstaller 静态分析遗漏）
    "gen_backends",
    "vision_backends",
    "prompt_templates",
    "prompt_optimizer",
    "services", "services.color_delta_e", "services.color_pdf",
    "colorflow_keys",
    "llm_keys",
    "colorflow_sdk", "colorflow_sdk.exceptions",
    "mcp_print", "mcp_print.tools.colors", "mcp_print.tools.cost", "mcp_print.tools",
    "rembg",
]

a = Analysis(
    [ENTRY],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pytest",
        "PySide6", "PyQt6", "PyQt5",
        "docx",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ColorFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    noconsole=True,
    icon=os.path.join(BASE_DIR, ICON_NAME),
    # cipher_block="AES",  # PyInstaller 6.x 已移除字节码加密；EXE 用 kwargs.get()
    #                      # 读取参数，该项被静默忽略，不产生任何加密效果。保留作追溯。
    disable_windowed_traceback=False,
)
