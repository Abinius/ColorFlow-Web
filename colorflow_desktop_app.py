# ColorFlow Desktop App — 原生桌面窗口
#
# 架构：
#   1. Flask 后端在后台线程启动（自动挑选空闲端口）
#   2. PyWebview 创建原生桌面窗口，加载 Flask 前端页面
#   3. 用户关闭窗口时自动停止 Flask 后端
#   4. 整个过程无浏览器标签页，完全原生窗口体验
#
# 打包: pyinstaller colorflow_desktop_app.spec

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import threading
import time
import traceback

HOST = "127.0.0.1"
DEFAULT_PORT = 5000
PORT_SCAN_LIMIT = 20       # 扫描 5000..5019
STARTUP_TIMEOUT = 30.0     # 等待后端就绪的总时长（秒）
LOG_PATH = pathlib.Path(os.environ.get("TEMP", ".")) / "colorflow_desktop.log"


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ============================================================
# 冻结环境补丁（必须在导入 app / rembg / pymatting 之前生效）
# ============================================================
def patch_numba_disk_cache():
    """关闭 numba 的磁盘缓存，修掉冻结环境下抠图（Alpha Matting）报 500 的问题。

    pymatting 的 njit 函数都显式写了 cache=True（例：pymatting/util/kdtree.py:7）。
    numba 要依据**函数源文件**推导缓存路径，而 PyInstaller 从 PYZ 导入的模块在磁盘上
    没有对应源文件，于是装饰期就抛（出处 numba/core/caching.py:423）：

        RuntimeError: cannot cache function '_make_tree':
                      no locator available for file 'pymatting\\util\\kdtree.py'

    该异常发生在 import pymatting.util.kdtree 时；pymatting 是请求期懒加载的，所以表现为
    /api/cutout 直接 500（且错误信息是一句看不出所以然的 RuntimeError）。

    这里把 njit/jit 的 cache 强制为 False（本就是 numba 的默认值）：JIT 编译与加速完全
    保留，只是不再落盘缓存。仅冻结环境生效，且幂等。
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        import numba
    except Exception as exc:
        log(f"numba 不可用，跳过磁盘缓存补丁（{exc}）")
        return

    for name in ("njit", "jit"):
        orig = getattr(numba, name, None)
        if orig is None or getattr(orig, "_colorflow_no_disk_cache", False):
            continue

        def _wrap(original):
            def wrapper(*args, **kwargs):
                kwargs["cache"] = False
                return original(*args, **kwargs)

            wrapper._colorflow_no_disk_cache = True
            wrapper.__name__ = getattr(original, "__name__", "wrapper")
            wrapper.__doc__ = getattr(original, "__doc__", None)
            return wrapper

        setattr(numba, name, _wrap(orig))
        log(f"已关闭 numba 磁盘缓存（numba.{name} → cache=False），规避冻结环境缓存定位失败")


patch_numba_disk_cache()


def setup_file_logging():
    """把标准 logging 的输出也写进桌面应用日志文件。

    打包用了 noconsole=True，进程没有控制台：Flask / werkzeug / 业务模块的 logger
    输出原本全部丢失。后端一旦在运行期报错（例如抠图 500），日志里只剩一句用户可见
    的错误，真正的异常堆栈无从追查。这里把根 logger 接到同一个日志文件上。
    """
    try:
        import logging

        root = logging.getLogger()
        if getattr(root, "_colorflow_file_handler", False):
            return
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
        )
        handler.setLevel(logging.INFO)
        root.addHandler(handler)
        if root.level == logging.NOTSET or root.level > logging.INFO:
            root.setLevel(logging.INFO)
        root._colorflow_file_handler = True
    except Exception as exc:
        log(f"配置日志文件失败（{exc}）")


setup_file_logging()


# ============================================================
# 错误提示
# ============================================================
def show_error(summary):
    """把失败原因告诉用户。

    打包时用了 noconsole=True，进程没有 stdin/stdout：既看不到 Traceback，
    也不能用 input() 等待（窗口模式下 input() 只会抛 RuntimeError 然后静默退出）。
    因此这里用系统弹窗，完整堆栈只写日志。
    """
    log(f"ERROR: {summary}")
    if os.name != "nt" or os.environ.get("COLORFLOW_NO_MSGBOX"):
        return
    try:
        import ctypes

        text = f"{summary}\n\n日志：{LOG_PATH}"
        # MB_ICONERROR | MB_SETFOREGROUND：确保弹窗出现在最前面
        ctypes.windll.user32.MessageBoxW(None, text, "ColorFlow 启动失败", 0x10 | 0x10000)
    except Exception as exc:
        log(f"系统弹窗不可用（{exc}），错误仅记录在日志中")


# ============================================================
# PyInstaller 路径处理
# ============================================================
def get_base_dir():
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).resolve().parent


def user_models_dir():
    """可写的用户级模型目录（Windows: %LOCALAPPDATA%\\ColorFlow\\models）。"""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    if not base:
        return None
    return pathlib.Path(base) / "ColorFlow" / "models"


def resolve_models_dir(base_dir):
    """确定 rembg 的模型目录（U2NET_HOME）。

    打包后包内 models/ 位于 PyInstaller 的一次性解包目录（_MEIPASS），进程退出即销毁。
    若把 U2NET_HOME 直接指向它，运行时下载的模型（例如 168MB 的 u2net_human_seg.onnx）
    下次启动就没了，rembg 也无法在包内缓存。所以优先用可写的用户目录，并把随包模型
    首次播种（copy）过去；任何一步失败都退回包内目录 —— 即改造前的老行为。
    """
    bundled = base_dir / "models"
    target = user_models_dir()
    if target is None:
        return bundled
    try:
        target.mkdir(parents=True, exist_ok=True)
        for src in sorted(bundled.glob("*.onnx")):
            dst = target / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                log(f"播种模型 → {dst}（{src.stat().st_size / 1048576:.1f} MB）")
        if any(target.glob("*.onnx")):
            return target
        log("用户模型目录为空且包内无模型，rembg 将按默认位置处理")
    except Exception as exc:
        log(f"用户模型目录不可用（{exc}），回退包内 models/")
    return bundled


# ============================================================
# .NET 运行时（pythonnet / pywebview 的依赖）
# ============================================================
# pythonnet 3.x 的 PyPI wheel 在 Windows 上只能走 CoreCLR：它的 netfx 加载器在本机
# 解析不到 Python.Runtime.Loader.Initialize（.NET Framework 会以 0x80131515 拒绝
# LoadFrom 该程序集），而 pywebview 的 Windows 后端又必须经 pythonnet。因此这里显式
# 指定 CoreCLR 运行时位置；用户已经设过环境变量时不覆盖，保持可定制。
DOTNET_ROOT_CANDIDATES = (
    ("LOCALAPPDATA", "Microsoft", "dotnet"),
    ("ProgramFiles", "dotnet"),
)

# clr_loader 自动生成的 runtimeconfig 只声明 Microsoft.NETCore.App，导致
# System.Windows.Forms（属于 WindowsDesktop 框架）解析不到，必须显式声明。
DOTNET_RUNTIME_CONFIG = {
    "runtimeOptions": {
        "tfm": "net8.0",
        "framework": {"name": "Microsoft.WindowsDesktop.App", "version": "8.0.0"},
        "configProperties": {
            "System.Reflection.Metadata.MetadataUpdater.IsSupported": False
        },
    }
}


def write_runtime_config(root):
    """把 runtimeconfig.json 写到可写的位置，返回路径（都不可写则返回 None）。"""
    candidates = [root]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(pathlib.Path(local) / "ColorFlow")
    candidates.append(pathlib.Path(tempfile.gettempdir()) / "ColorFlow")
    for directory in candidates:
        path = pathlib.Path(directory) / "pythonnet.runtimeconfig.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(json.dumps(DOTNET_RUNTIME_CONFIG, indent=2), encoding="utf-8")
            return path
        except OSError as exc:
            log(f"runtimeconfig 写入 {path} 失败：{exc}")
    return None


def setup_dotnet_runtime():
    """为 pythonnet 指定 .NET CoreCLR 运行时；找不到则什么都不做。"""
    if os.environ.get("PYTHONNET_RUNTIME") or os.environ.get("DOTNET_ROOT"):
        log(
            "沿用已有 .NET 配置："
            f"PYTHONNET_RUNTIME={os.environ.get('PYTHONNET_RUNTIME')} "
            f"DOTNET_ROOT={os.environ.get('DOTNET_ROOT')}"
        )
        return
    for parts in DOTNET_ROOT_CANDIDATES:
        base = os.environ.get(parts[0])
        if not base:
            continue
        root = pathlib.Path(base).joinpath(*parts[1:])
        if not ((root / "host" / "fxr").is_dir() and (root / "shared").is_dir()):
            continue
        config = write_runtime_config(root)
        os.environ["DOTNET_ROOT"] = str(root)
        os.environ["PYTHONNET_RUNTIME"] = "coreclr"
        if config is not None:
            os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(config)
        log(f"使用 .NET 运行时: {root}（runtimeconfig: {config}）")
        return
    log("未找到 .NET 运行时；pywebview 将无法初始化窗口（见下方报错与 README 说明）")


def setup_environment():
    base_dir = get_base_dir()
    os.chdir(base_dir)
    log(f"工作目录: {base_dir}")

    setup_dotnet_runtime()

    models_dir = resolve_models_dir(base_dir)
    if models_dir.is_dir():
        os.environ["U2NET_HOME"] = str(models_dir)
        names = sorted(p.name for p in models_dir.glob("*.onnx"))
        log(f"U2NET_HOME: {models_dir}")
        log(f"可用模型: {', '.join(names) if names else '(无，rembg 将尝试联网下载)'}")

    output_dir = pathlib.Path(tempfile.gettempdir()) / "colorflow-output"
    output_dir.mkdir(exist_ok=True)
    os.environ["COLORFLOW_OUTPUT_DIR"] = str(output_dir)
    log(f"输出目录: {output_dir}")


# ============================================================
# 端口选择
# ============================================================
def port_is_free(port):
    """能否在 HOST:port 上独占监听。

    Windows 上必须加 SO_EXCLUSIVEADDRUSE：否则别的进程已占用该端口时本进程仍可能
    bind 成功，检查就形同虚设。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        except (AttributeError, OSError):
            pass
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def http_get(port, path, timeout=2.0):
    """返回 (status, body)；连接失败返回 (None, None)。"""
    import http.client

    try:
        conn = http.client.HTTPConnection(HOST, port, timeout=timeout)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, resp.read().decode("utf-8", "replace")
        finally:
            conn.close()
    except Exception:
        return None, None


def colorflow_instance(port):
    """该端口上若运行着 ColorFlow，返回其 /healthz 信息 dict，否则 None。

    用 /healthz 的固定字段（status=ok + uptime_s + checks）做指纹，避免把恰好占了
    5000 的其它服务误认成自家服务 —— 旧实现只探测“GET / 有没有响应”，端口被旧进程
    占用时会静默连上别人的服务且毫无提示。
    """
    status, body = http_get(port, "/healthz")
    if status == 200 and body:
        try:
            data = json.loads(body)
        except ValueError:
            return None
        if isinstance(data, dict) and data.get("status") == "ok" and "uptime_s" in data and "checks" in data:
            return data
        return None
    # 兼容没有 /healthz 的旧版本
    status, body = http_get(port, "/")
    if status == 200 and body and "ColorFlow" in body:
        return {"status": "ok", "legacy": True}
    return None


def backend_ready(port):
    """后端是否已可服务（优先用轻量的 /healthz，旧版本退化为 /）。"""
    if http_get(port, "/healthz")[0] == 200:
        return True
    return http_get(port, "/")[0] == 200


def choose_port():
    """返回 (port, note)。显式指定 PORT 时严格遵从，否则从 5000 起找第一个空闲端口。"""
    forced = os.environ.get("PORT")
    if forced:
        try:
            port = int(forced)
        except ValueError:
            raise RuntimeError(f"环境变量 PORT 不是合法端口号: {forced!r}") from None
        if not port_is_free(port):
            other = colorflow_instance(port)
            who = f"另一个 ColorFlow 实例（pid {other.get('pid')}）" if other else "其它程序"
            raise RuntimeError(f"PORT={port} 已被{who}占用；显式指定时不会自动换端口")
        return port, f"{port}（PORT 显式指定）"

    skipped = []
    for port in range(DEFAULT_PORT, DEFAULT_PORT + PORT_SCAN_LIMIT):
        if port_is_free(port):
            return port, f"{port}（自动选择）"
        other = colorflow_instance(port)
        if other:
            info = "另一个 ColorFlow 实例"
            if other.get("pid") is not None:
                info += f"（pid {other.get('pid')}, uptime {other.get('uptime_s')}s）"
            skipped.append(f"{port}={info}")
        else:
            skipped.append(f"{port}=被其它程序占用")
    raise RuntimeError(
        f"{DEFAULT_PORT}-{DEFAULT_PORT + PORT_SCAN_LIMIT - 1} 均不可用: " + ", ".join(skipped)
    )


# ============================================================
# Flask 后端管理
# ============================================================
def start_flask_backend(port):
    """在后台线程启动 Flask，等待端口就绪。

    返回 (thread, holder)；holder["error"] 记录线程内的启动异常（例如端口竞态导致
    Address already in use），供调用方区分“还没起来”和“已经失败”。
    """
    import app

    holder = {}

    def run():
        try:
            app.app.run(host=HOST, port=port, debug=False, use_reloader=False, threaded=True)
        except Exception as exc:
            holder["error"] = exc
            log(f"Flask 线程退出: {type(exc).__name__}: {exc}")

    flask_thread = threading.Thread(target=run, daemon=True, name="colorflow-flask")
    flask_thread.start()
    log(f"Flask 线程已启动, 等待 {HOST}:{port} 就绪 ...")

    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if "error" in holder:
            return flask_thread, holder
        if backend_ready(port):
            log(f"后端就绪: http://{HOST}:{port}")
            return flask_thread, holder
        time.sleep(0.4)
    return flask_thread, holder


# ============================================================
# 主入口
# ============================================================
def main():
    try:
        log("=" * 40)
        log("ColorFlow Desktop 原生桌面应用启动")

        setup_environment()

        port, note = choose_port()
        log(f"端口: {note}")

        # 线程对象仅用于调试观察，不参与后续逻辑（保持返回以便排查）
        _flask_thread, holder = start_flask_backend(port)
        if "error" in holder:
            raise RuntimeError(f"后端启动失败（{HOST}:{port}）：{holder['error']}")
        if not backend_ready(port):
            raise RuntimeError(f"后端在 {STARTUP_TIMEOUT:.0f}s 内未就绪（{HOST}:{port}）")

        # /healthz 会回报后端自己的 pid。若探测到的不是本进程，说明端口上跑的是
        # 另一个 ColorFlow 实例（竞态或旧进程残留），此时绝不能把窗口指过去 ——
        # 否则用户看到/操作的是别人的服务，且毫无提示。
        identity = colorflow_instance(port)
        if identity and identity.get("pid") not in (None, os.getpid()):
            raise RuntimeError(
                f"{HOST}:{port} 上是另一个 ColorFlow 实例（pid {identity['pid']}，"
                f"本进程 {os.getpid()}），拒绝连接"
            )
        if identity:
            log(f"后端身份校验通过: pid {identity.get('pid')}, uptime {identity.get('uptime_s')}s")

        log("初始化 PyWebview 窗口...")
        import webview

        # 显式指定窗口图标。不指定时 pywebview 会退化为 ExtractIconW(sys.executable)：
        # 打包后能取到 exe 内嵌图标，但**从源码运行**取到的是 python.exe 的图标。
        # 注意 icon 是 webview.start() 的参数（不是 create_window 的）——它写入
        # _state['icon']，winforms 后端在建窗时读取；文档虽写"仅 GTK/QT"，但该分支
        # 在 Windows 上同样生效。图标同时由 spec 打进包内，frozen 时从 _MEIPASS 读取。
        # colorflow.ico 是「深色方块 + 实心白 M」：深色方块保证浅色背景上清楚，实心白 M
        # 保证深色背景上仍可辨认。（若把 M 做成透明镂空，深色背景下方块与 M 会一起消失 ——
        # 那正是这个图标的原始缺陷。）
        icon_path = get_base_dir() / "colorflow.ico"
        if icon_path.is_file():
            log(f"窗口图标: {icon_path}")
        else:
            log("未找到 colorflow.ico；窗口图标将回退为 exe/解释器自带图标")

        webview.create_window(
            title="ColorFlow - AI 矢量描图工具",
            url=f"http://{HOST}:{port}",
            width=1400,
            height=900,
            min_size=(1000, 700),
            resizable=True,
            fullscreen=False,
            confirm_close=True,
        )

        webview.start(debug=False, icon=str(icon_path) if icon_path.is_file() else None)

    except Exception as exc:
        log("启动失败:\n" + traceback.format_exc())
        show_error(f"ColorFlow 启动失败：{type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
