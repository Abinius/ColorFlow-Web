# ColorFlow Web — 重启脚本
# 杀掉 5000 端口旧进程，启动新实例
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File restart.ps1
$ErrorActionPreference = "SilentlyContinue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 加载虚拟环境
$env:Path = Join-Path $scriptDir ".venv\Scripts" + ";" + $env:Path

# 设置模型缓存目录（指向包内 models\，避免联网下载）
if (Test-Path (Join-Path $scriptDir "models")) {
    $env:U2NET_HOME = Join-Path $scriptDir "models"
}

# 杀掉 5000 端口旧进程（LISTENING 状态）
$pids = netstat -ano | Select-String ":5000\s+LISTENING" | ForEach-Object { ($_.Line -split "\s+")[4] }
foreach ($pid in $pids) {
    if ($pid -and $pid -ne "0") {
        try { Stop-Process -Id $pid -Force } catch {}
    }
}
Start-Sleep -Seconds 1

# 启动新实例（后台，不阻塞）
$env:FLASK_DEBUG = "false"
Start-Process -FilePath "python" -ArgumentList (Join-Path $scriptDir "app.py") -WorkingDirectory $scriptDir -WindowStyle Hidden

Write-Host "ColorFlow restarted on port 5000."