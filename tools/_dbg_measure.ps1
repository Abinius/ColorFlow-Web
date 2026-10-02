param([int]$Width = 1400, [int]$Height = 1000)
$ErrorActionPreference = "Stop"
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$url = "file:///" + ($env:TEMP -replace '\\','/') + "/cf_gen_preview.html"
$udd = Join-Path $env:TEMP ("edge_cdp_" + $Width)
if (Test-Path $udd) { Remove-Item $udd -Recurse -Force -ErrorAction SilentlyContinue }

$proc = Start-Process -FilePath $edge -PassThru -ArgumentList @(
  "--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check",
  "--remote-debugging-port=9222","--force-device-scale-factor=1",
  "--window-size=$Width,$Height","--user-data-dir=$udd", $url
)
try {
  $list = $null
  for ($i=0; $i -lt 40; $i++) {
    try { $list = Invoke-RestMethod "http://127.0.0.1:9222/json/list" -TimeoutSec 2; if ($list) { break } } catch {}
    Start-Sleep -Milliseconds 250
  }
  if (-not $list) { throw "CDP endpoint did not come up" }
  $page = $list | Where-Object { $_.type -eq "page" -and $_.webSocketDebuggerUrl } | Select-Object -First 1
  if (-not $page) { throw "no page target" }

  # wait for metrics to render
  Start-Sleep -Seconds 2

  $ws = New-Object System.Net.WebSockets.ClientWebSocket
  $ws.ConnectAsync([Uri]$page.webSocketDebuggerUrl, [Threading.CancellationToken]::None).Wait(5000) | Out-Null

  function Send-Ws($ws, $obj) {
    $json = $obj | ConvertTo-Json -Depth 10 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $seg = [ArraySegment[byte]]::new($bytes)
    $ws.SendAsync($seg, [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).Wait(5000) | Out-Null
  }
  function Recv-Ws($ws) {
    $buf = New-Object byte[] 131072
    $ms = New-Object IO.MemoryStream
    do {
      $seg = [ArraySegment[byte]]::new($buf)
      $t = $ws.ReceiveAsync($seg, [Threading.CancellationToken]::None)
      $t.Wait(5000) | Out-Null
      $ms.Write($buf, 0, $t.Result.Count)
    } while (-not $t.Result.EndOfMessage)
    return [Text.Encoding]::UTF8.GetString($ms.ToArray())
  }

  $expr = '(function(){var el=document.getElementById("__m"); return el ? el.textContent : "NOT_READY";})()'
  Send-Ws $ws (@{ id = 1; method = "Runtime.evaluate"; params = @{ expression = $expr; returnByValue = $true } })
  $resp = $null
  for ($i=0; $i -lt 20; $i++) {
    $msg = Recv-Ws $ws
    $j = $msg | ConvertFrom-Json
    if ($j.id -eq 1) { $resp = $j; break }
  }
  if ($resp) { Write-Host $resp.result.result.value } else { Write-Host "NO RESPONSE" }
  $ws.CloseAsync([Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "bye", [Threading.CancellationToken]::None).Wait(2000) | Out-Null
} finally {
  Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 500
  Remove-Item $udd -Recurse -Force -ErrorAction SilentlyContinue
}
