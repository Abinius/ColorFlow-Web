# Build the ColorFlow desktop executable, keeping artifacts inside the repository.
#
# Why this script exists
# ----------------------
# PyInstaller creates build/ and dist/ relative to the CURRENT WORKING DIRECTORY, and it
# does so in build_main.py *before* running the .spec file. Calling pyinstaller from
# somewhere else therefore scattered the artifacts outside the repo (this project used to
# drop them into D:\Abin\abincheung\WEB\). The spec file also pins CONF['distpath'] /
# CONF['workpath'], but that cannot help when the working directory is not writable
# (PyInstaller fails at the eager makedirs step before the spec even runs). So this script
# always passes the paths explicitly.
#
# Keep this file ASCII-only: Windows PowerShell 5.1 reads .ps1 files without a BOM as GBK,
# which corrupts non-ASCII text during parsing.
#
# Usage:
#   .\tools\build_desktop.ps1
#   .\tools\build_desktop.ps1 -BundleU2net     # also bundle the 168MB u2net_human_seg model

[CmdletBinding()]
param(
    [switch]$BundleU2net
)

$ErrorActionPreference = 'Stop'

$base = Split-Path -Parent $PSScriptRoot
$pyinstaller = Join-Path $base '.venv\Scripts\pyinstaller.exe'
$spec = Join-Path $base 'colorflow_desktop_app.spec'
$distpath = Join-Path $base 'dist'
$workpath = Join-Path $base 'build'

if (-not (Test-Path $pyinstaller)) {
    throw "pyinstaller not found at $pyinstaller - create .venv and install requirements-desktop.txt first"
}
if (-not (Test-Path $spec)) {
    throw "spec not found at $spec"
}

if ($BundleU2net) {
    $env:COLORFLOW_BUNDLE_U2NET = '1'
    Write-Host '[build] bundling u2net_human_seg.onnx (adds ~168 MB)'
} else {
    Remove-Item Env:\COLORFLOW_BUNDLE_U2NET -ErrorAction SilentlyContinue
}

Write-Host "[build] spec     : $spec"
Write-Host "[build] distpath : $distpath"
Write-Host "[build] workpath : $workpath"
Write-Host ''

& $pyinstaller --noconfirm --distpath $distpath --workpath $workpath $spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $distpath 'ColorFlow.exe'
if (-not (Test-Path $exe)) {
    throw "build reported success but $exe is missing"
}

$item = Get-Item $exe
Write-Host ''
Write-Host ("[build] done: " + $item.FullName)
Write-Host ("[build] size: " + [math]::Round($item.Length / 1MB, 1) + " MB")
Write-Host '[build] note: the exe still needs a .NET runtime on the target machine;'
Write-Host '[build]       the app looks for it under %LOCALAPPDATA%\Microsoft\dotnet or %ProgramFiles%\dotnet.'
