param([int]$Width = 1400)
$ErrorActionPreference = "Stop"
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$url = "file:///" + ($env:TEMP -replace '\\','/') + "/cf_gen_preview.html"
$dump = & $edge --headless=new --disable-gpu --force-device-scale-factor=1 --window-size="$Width,1000" --virtual-time-budget=3000 --dump-dom $url 2>$null
$text = $dump -join "`n"
if ($text -match '(?s)<pre id="__m">(.*?)</pre>') {
    $m = $matches[1]
    $m = $m -replace '&gt;','>' -replace '&lt;','<' -replace '&amp;','&'
    Write-Host $m
} else {
    Write-Host "NO METRICS FOUND (dump length $($text.Length))"
}
