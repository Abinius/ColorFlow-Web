$ErrorActionPreference = "Stop"
$r = Invoke-WebRequest -Uri "http://127.0.0.1:5000/" -UseBasicParsing -TimeoutSec 15
$html = $r.Content
$html = $html -replace '<head>', "<head>`n<base href=`"http://127.0.0.1:5000/`">"
$html = $html -replace '<button class="tab active" data-tab="trace">', '<button class="tab" data-tab="trace">'
$html = $html -replace '<button class="tab" data-tab="generate">', '<button class="tab active" data-tab="generate">'
$html = $html -replace '<section class="tab-content active" id="tab-trace">', '<section class="tab-content" id="tab-trace">'
$html = $html -replace '<section class="tab-content" id="tab-generate">', '<section class="tab-content active" id="tab-generate">'

$metrics = @'
<script>
window.addEventListener('load', function () {
  setTimeout(function () {
    var winW = document.documentElement.clientWidth;
    var L = [];
    L.push('winW=' + winW + ' docScrollW=' + document.documentElement.scrollWidth);
    var root = document.getElementById('tab-generate');
    var sels = ['.gen-layout','.gen-input','.gen-output','.gen-results','.gen-mode-toggle','.gen-mode-btns','.gen-prompt-area','.gen-prompt-input','.gen-optimize-btn','.gen-template-section','.gen-template-header','.gen-tpl-actions','.gen-opts','.gen-ref-zone','.gen-reverse-block','.gen-reverse-zone','#genReverseBtn','#genSaveRefBtn','.gen-ref-gallery','#genBtn'];
    sels.forEach(function (s) {
      root.querySelectorAll(s).forEach(function (el, i) {
        var rc = el.getBoundingClientRect();
        var over = el.scrollWidth > el.clientWidth + 1 ? (' INTERNALOVERFLOW sw=' + el.scrollWidth + ' cw=' + el.clientWidth) : '';
        L.push(s + '[' + i + '] x=' + Math.round(rc.x) + ' y=' + Math.round(rc.y) + ' w=' + Math.round(rc.width) + ' h=' + Math.round(rc.height) + over);
      });
    });
    var rows = root.querySelectorAll('.gen-opts .param-row, .gen-input > .param-row');
    rows.forEach(function (el, i) {
      var rc = el.getBoundingClientRect();
      var lbl = el.querySelector('label');
      var sel = el.querySelector('select, textarea, .upload-zone, .gen-prompt-area');
      var extra = '';
      if (lbl) { var lr = lbl.getBoundingClientRect(); extra += ' labelW=' + Math.round(lr.width) + ' labelH=' + Math.round(lr.height); }
      if (sel) { var sr = sel.getBoundingClientRect(); extra += ' fieldW=' + Math.round(sr.width); }
      L.push('row[' + i + '] w=' + Math.round(rc.width) + extra);
    });
    var bad = [];
    root.querySelectorAll('*').forEach(function (el) {
      var rc = el.getBoundingClientRect();
      if (rc.width === 0 && rc.height === 0) return;
      if (rc.right > winW + 2 || rc.left < -2) {
        bad.push(el.tagName + '.' + (el.className || '').toString().split(' ').slice(0, 2).join('.') + ' right=' + Math.round(rc.right) + ' w=' + Math.round(rc.width));
      }
    });
    L.push('OVERFLOW_ELEMENTS(' + bad.length + '):');
    bad.slice(0, 40).forEach(function (b) { L.push('  ' + b); });
    var pre = document.createElement('pre');
    pre.id = '__m';
    pre.textContent = L.join('\n');
    document.body.appendChild(pre);
  }, 800);
});
</script>
'@
$html = $html -replace '</body>', ($metrics + "`n</body>")
$tmpHtml = Join-Path $env:TEMP "cf_gen_preview.html"
[System.IO.File]::WriteAllText($tmpHtml, $html, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "temp html ready: $tmpHtml"
