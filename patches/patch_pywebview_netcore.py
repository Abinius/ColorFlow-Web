#!/usr/bin/env python3
"""让 pywebview 6.2.1 的 Windows 后端在 .NET Core / .NET 8 下可用。

背景
====
pythonnet 3.x 的 PyPI wheel 在本机走不了 .NET Framework：它的 netfx 加载器解析不到
Python.Runtime.Loader.Initialize，根因是 .NET Framework 以 0x80131515 拒绝
Assembly.LoadFrom/LoadFile 该程序集（ReflectionOnlyLoadFrom 与 Load(byte[]) 却可以）。
因此只能走 CoreCLR，而 pywebview 6.2.1（截至 2026-10 的最新版，PyPI 上共 52 个版本）
的 Windows 后端有三处 .NET Framework 假设，在 CoreCLR 下会逐一失败：

  1. ``from Microsoft.Win32 import SystemEvents``
     .NET Framework 里该类型在 System.dll 中；.NET Core 里它在独立程序集
     Microsoft.Win32.SystemEvents.dll 内，必须先 AddReference。
  2. ``OpenFolderDialog`` 的**类体**里解析 ``FileDialogNative+IFileDialog``、
     ``FileDialog+VistaDialogEvents``、``FileDialogNative+FOS`` 等 .NET Framework
     专有嵌套类型；.NET Core 下 GetType() 返回 None，整个模块 import 失败。
  3. 自带的 ``Microsoft.Web.WebView2.{Core,WinForms}.dll`` 是 net4x 构建，引用了
     .NET Core 已移除的 ``System.Windows.Forms.ContextMenu``。

本脚本幂等地修掉这三点：前两点改 ``webview/platforms/winforms.py``，第三点换成
WebView2 NuGet 包里的 netcoreapp3.0 构建（该包从某个版本起不再提供 netcoreapp，
故版本固定为 1.0.1774.30）。

用法
====
    .venv\\Scripts\\python.exe patches\\patch_pywebview_netcore.py
    .venv\\Scripts\\python.exe patches\\patch_pywebview_netcore.py --nupkg <本地.nupkg>
    .venv\\Scripts\\python.exe patches\\patch_pywebview_netcore.py --check   # 只检查不改

回滚：被改动的文件都备份为同目录下的 ``<文件名>.orig``，直接覆盖回去即可。
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import textwrap
import urllib.request
import zipfile
from pathlib import Path

WEBVIEW2_VERSION = "1.0.1774.30"
NUPKG_URL = (
    "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/"
    f"{WEBVIEW2_VERSION}/microsoft.web.webview2.{WEBVIEW2_VERSION}.nupkg"
)
WEBVIEW2_DLLS = (
    "Microsoft.Web.WebView2.Core.dll",
    "Microsoft.Web.WebView2.WinForms.dll",
)
MARKER = "patched-by-colorflow"

WINFORMS_HELPERS = '''
class _CFSafeType:
    """{marker}: 占位类型，替代 .NET Core 上不存在的 .NET Framework 嵌套类型。"""

    def __getattr__(self, name):
        return lambda *a, **k: _CFSafeType()


class _CFSafeAssembly:
    """{marker}: GetType 永不返回 None。

    pywebview 的 OpenFolderDialog 在类体里链式调用
    windowsFormsAssembly.GetType(...).GetMethod(...)；.NET Core 上 GetType 返回 None
    会让整个模块 import 失败。换成中性占位后模块可正常导入，只有「选择文件夹」式
    对话框受影响。
    """

    def __init__(self, inner):
        self._inner = inner

    def GetType(self, name):
        found = self._inner.GetType(name)
        return found if found is not None else _CFSafeType()

    def __getattr__(self, name):
        return getattr(self._inner, name)

'''.format(marker=MARKER)


def patch_winforms(path: Path, check: bool) -> bool:
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        print(f"  [已打过] {path.name}")
        return True

    anchor = re.search(r"(?m)^([ \t]*)import System\.Windows\.Forms as WinForms", source)
    if not anchor:
        print(f"  [失败] {path} 中找不到 System.Windows.Forms 的导入锚点")
        return False
    indent = anchor.group(1)

    insertion = (
        "import System.Windows.Forms as WinForms\n\n"
        + textwrap.indent(WINFORMS_HELPERS.strip("\n"), indent)
        + "\n\n"
        + indent
        + "try:\n"
        + indent
        + "    clr.AddReference('Microsoft.Win32.SystemEvents')\n"
        + indent
        + "except Exception:\n"
        + indent
        + "    pass\n"
    )
    patched = source[: anchor.start()] + insertion + source[anchor.end():]

    patched, count = re.subn(
        r"(?m)^([ \t]*)windowsFormsAssembly = Assembly\.LoadWithPartialName"
        r"\('System\.Windows\.Forms'\)",
        r"\1windowsFormsAssembly = _CFSafeAssembly("
        r"Assembly.LoadWithPartialName('System.Windows.Forms'))",
        patched,
    )
    if count != 1:
        print(f"  [失败] {path} 中找不到 OpenFolderDialog 的 windowsFormsAssembly 锚点")
        return False

    if check:
        print(f"  [待修改] {path}")
        return True
    shutil.copy2(path, path.with_suffix(path.suffix + ".orig"))
    path.write_text(patched, encoding="utf-8")
    print(f"  [已修补] {path}（原文件备份为 {path.name}.orig）")
    return True


def fetch_nupkg(explicit: Path | None) -> Path | None:
    if explicit is not None:
        if not explicit.is_file():
            print(f"  [失败] 指定的 nupkg 不存在：{explicit}")
            return None
        return explicit
    cache = Path(__file__).resolve().parent / f"webview2-{WEBVIEW2_VERSION}.nupkg"
    if cache.is_file() and cache.stat().st_size > 1_000_000:
        print(f"  [已缓存] {cache.name}")
        return cache
    print(f"  下载 {NUPKG_URL}")
    try:
        with urllib.request.urlopen(NUPKG_URL, timeout=120) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001 - 网络问题种类多，统一提示替代方案
        print(f"  [失败] 下载失败：{exc}")
        print("         请手动下载后用 --nupkg 指定：")
        print(f"         {NUPKG_URL}")
        return None
    cache.write_bytes(data)
    print(f"  [已下载] {cache.name}（{len(data) / 1024:.0f} KB）")
    return cache


def patch_webview2(lib_dir: Path, nupkg: Path, check: bool) -> bool:
    target_sizes = {}
    try:
        with zipfile.ZipFile(nupkg) as archive:
            for name in WEBVIEW2_DLLS:
                member = f"lib/netcoreapp3.0/{name}"
                target_sizes[name] = archive.getinfo(member).file_size
    except (KeyError, zipfile.BadZipFile) as exc:
        print(f"  [失败] 从 nupkg 读取 netcoreapp3.0 程序集失败：{exc}")
        return False

    for name in WEBVIEW2_DLLS:
        dst = lib_dir / name
        if not dst.is_file():
            print(f"  [失败] 找不到 {dst}")
            return False
        if dst.stat().st_size == target_sizes[name]:
            print(f"  [已是 netcoreapp3.0] {name}")
            continue
        if check:
            print(f"  [待替换] {name}：{dst.stat().st_size} -> {target_sizes[name]} 字节")
            continue
        shutil.copy2(dst, dst.with_suffix(dst.suffix + ".orig"))
        with zipfile.ZipFile(nupkg) as archive:
            data = archive.read(f"lib/netcoreapp3.0/{name}")
        dst.write_bytes(data)
        print(f"  [已替换] {name}：{target_sizes[name]} 字节（原文件备份为 {name}.orig）")

    if not check:
        _drop_stale_pycache(lib_dir.parent)
    return True


def _drop_stale_pycache(package_root: Path) -> None:
    removed = 0
    for cache in package_root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
        removed += 1
    if removed:
        print(f"  [清理] 移除 {removed} 个 __pycache__，确保改动后的模块重新编译")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nupkg", type=Path, default=None,
                        help="本地 Microsoft.Web.WebView2 .nupkg（离线时使用）")
    parser.add_argument("--check", action="store_true", help="只检查当前状态，不做修改")
    args = parser.parse_args()

    try:
        import webview
    except ImportError:
        print("在解释器里找不到 pywebview；请用项目 .venv 的 python 运行本脚本")
        return 1

    package_root = Path(webview.__file__).resolve().parent
    print(f"pywebview: {package_root}")
    print("1) 修补 webview/platforms/winforms.py")
    ok = patch_winforms(package_root / "platforms" / "winforms.py", args.check)

    print("2) 替换自带的 WebView2 程序集为 netcoreapp3.0 构建")
    lib_dir = package_root / "lib"
    nupkg = fetch_nupkg(args.nupkg)
    if nupkg is not None:
        ok = patch_webview2(lib_dir, nupkg, args.check) and ok

    print("完成" if ok else "存在失败项，见上方输出")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
