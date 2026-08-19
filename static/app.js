// === XSS 防护：把任意字符串安全插入 innerHTML ===
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = String(str ?? '');
  return div.innerHTML;
}

// ΔE 分级（Figma match-de 配色）
function gradeClass(de) {
  return de < 1 ? 'excellent' : de < 3 ? 'good' : de < 6 ? 'fair' : 'poor';
}

// === API Key：localStorage 持久化 + 自动附带 x-api-key 头 ===
const apiKeyInput = document.getElementById('apiKeyInput');
const apiKeyBtn = document.getElementById('apiKeyBtn');

apiKeyInput.value = localStorage.getItem('colorflow_api_key') || '';
apiKeyBtn.addEventListener('click', () => {
  const key = apiKeyInput.value.trim();
  if (key) {
    localStorage.setItem('colorflow_api_key', key);
    apiKeyBtn.textContent = '✓ 已保存';
  } else {
    localStorage.removeItem('colorflow_api_key');
    apiKeyBtn.textContent = '已清除';
  }
  setTimeout(() => { apiKeyBtn.textContent = '保存'; }, 1200);
});

function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const key = localStorage.getItem('colorflow_api_key');
  if (key) headers.set('x-api-key', key);
  options.headers = headers;
  return fetch(url, options);
}

// === Sidebar（DeepSeek Harness 式左栏抽屉，≤960px） ===
const sidebar = document.getElementById('sidebar');
const scrim = document.getElementById('scrim');
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebarClose = document.getElementById('sidebarClose');

function openSidebar() {
  sidebar.classList.add('open');
  scrim.classList.add('show');
}
function closeSidebar() {
  sidebar.classList.remove('open');
  scrim.classList.remove('show');
}

if (sidebarToggle) sidebarToggle.addEventListener('click', openSidebar);
if (sidebarClose) sidebarClose.addEventListener('click', closeSidebar);
if (scrim) scrim.addEventListener('click', closeSidebar);
window.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeSidebar();
    closeSettingsModal();
  }
});

// === Settings Modal ===
const settingsModal = document.getElementById('settingsModal');
const settingsToggle = document.getElementById('settingsToggle');
const settingsClose = document.getElementById('settingsClose');
const settingsBackdrop = document.getElementById('settingsBackdrop');

function openSettingsModal() {
  settingsModal.classList.add('open');
}
function closeSettingsModal() {
  settingsModal.classList.remove('open');
}

if (settingsToggle) settingsToggle.addEventListener('click', openSettingsModal);
if (settingsClose) settingsClose.addEventListener('click', closeSettingsModal);
if (settingsBackdrop) settingsBackdrop.addEventListener('click', closeSettingsModal);

// === Tab Navigation ===
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    // 移动端点击导航后自动收起抽屉
    if (window.matchMedia('(max-width: 960px)').matches) closeSidebar();
  });
});

// === Vector Trace ===
const uploadZone = document.getElementById('uploadZone');
const traceFile = document.getElementById('traceFile');
const previewImg = document.getElementById('previewImg');
const traceBtn = document.getElementById('traceBtn');
const svgPreview = document.getElementById('svgPreview');
const svgInfo = document.getElementById('svgInfo');
const downloadSvg = document.getElementById('downloadSvg');
const filterSpeckle = document.getElementById('filterSpeckle');
const speckleVal = document.getElementById('speckleVal');
const pathPrecision = document.getElementById('pathPrecision');
const precisionVal = document.getElementById('precisionVal');

let currentSvgBase64 = null;

filterSpeckle.addEventListener('input', () => speckleVal.textContent = filterSpeckle.value);
pathPrecision.addEventListener('input', () => precisionVal.textContent = pathPrecision.value);

uploadZone.addEventListener('click', () => traceFile.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files[0]) {
    traceFile.files = e.dataTransfer.files;
    handleFile(e.dataTransfer.files[0]);
  }
});

traceFile.addEventListener('change', e => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

function handleFile(file) {
  if (!file.type.startsWith('image/')) {
    alert('请上传图片文件');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('图片不能超过 10MB');
    return;
  }
  const reader = new FileReader();
  reader.onload = e => {
    previewImg.src = e.target.result;
    previewImg.classList.remove('hidden');
    uploadZone.querySelector('.upload-placeholder').classList.add('hidden');
    traceBtn.disabled = false;
  };
  reader.readAsDataURL(file);
}

traceBtn.addEventListener('click', async () => {
  if (!traceFile.files[0]) return;
  traceBtn.disabled = true;
  traceBtn.querySelector('.btn-text').classList.add('hidden');
  traceBtn.querySelector('.btn-loader').classList.remove('hidden');

  const formData = new FormData();
  formData.append('image', traceFile.files[0]);
  formData.append('mode', document.getElementById('traceMode').value);
  formData.append('filter_speckle', filterSpeckle.value);
  formData.append('path_precision', pathPrecision.value);
  formData.append('ignore_white', document.getElementById('ignoreWhite').checked ? '1' : '0');

  try {
    const resp = await apiFetch('/api/trace', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.success) {
      currentSvgBase64 = data.svg_base64;
      const svgEl = `<img src="data:image/svg+xml;base64,${data.svg_base64}" alt="SVG Output" />`;
      svgPreview.innerHTML = svgEl;
      svgInfo.classList.remove('hidden');
      svgInfo.querySelector('.svg-size').textContent = `${(data.size / 1024).toFixed(1)} KB`;
    } else {
      svgPreview.innerHTML = `<div class="svg-placeholder" style="color:var(--error)">错误: ${escapeHtml(data.error)}</div>`;
    }
  } catch (e) {
    svgPreview.innerHTML = `<div class="svg-placeholder" style="color:var(--error)">请求失败: ${escapeHtml(e)}</div>`;
  } finally {
    traceBtn.disabled = false;
    traceBtn.querySelector('.btn-text').classList.remove('hidden');
    traceBtn.querySelector('.btn-loader').classList.add('hidden');
  }
});

downloadSvg.addEventListener('click', () => {
  if (!currentSvgBase64) return;
  const a = document.createElement('a');
  a.href = 'data:image/svg+xml;base64,' + currentSvgBase64;
  a.download = 'colorflow_output.svg';
  a.click();
});

// === 导出印刷 PDF（export_print 前端入口） ===
const exportPdfBtn = document.getElementById('exportPdfBtn');
const exportPanel = document.getElementById('exportPanel');

exportPdfBtn.addEventListener('click', () => {
  if (!traceFile.files[0]) return;
  exportPanel.classList.remove('hidden');
  document.getElementById('exportPdfConfirm').disabled = false;
});

document.getElementById('exportPdfCancel').addEventListener('click', () => {
  exportPanel.classList.add('hidden');
});

document.getElementById('exportPdfConfirm').addEventListener('click', async () => {
  const w = parseFloat(document.getElementById('expWidth').value);
  const h = parseFloat(document.getElementById('expHeight').value);
  const b = parseFloat(document.getElementById('expBleed').value) || 0;
  if (!w || !h) { alert('请输入成品尺寸'); return; }
  const btn = document.getElementById('exportPdfConfirm');
  btn.disabled = true; btn.textContent = '生成中...';
  try {
    const formData = new FormData();
    formData.append('image', traceFile.files[0]);
    formData.append('width_mm', String(w));
    formData.append('height_mm', String(h));
    formData.append('bleed_mm', String(b));
    formData.append('mode', document.getElementById('traceMode').value);
    const resp = await apiFetch('/api/print/export', { method: 'POST', body: formData });
    if (!resp.ok) {
      const d = await resp.json().catch(() => ({}));
      alert('导出失败: ' + (d.error || resp.status));
      return;
    }
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'colorflow_print.pdf';
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    alert('导出失败: ' + e);
  } finally {
    btn.disabled = false; btn.textContent = '生成印刷 PDF';
    exportPanel.classList.add('hidden');
  }
});

// === 一键流水线：提取主色 & Pantone 匹配 ===
const colorMatchBtn = document.getElementById('colorMatchBtn');
const paletteResults = document.getElementById('paletteResults');

colorMatchBtn.addEventListener('click', async () => {
  if (!traceFile.files[0]) return;
  colorMatchBtn.disabled = true;
  colorMatchBtn.textContent = '提取中...';
  paletteResults.classList.remove('hidden');
  paletteResults.innerHTML = '<div class="match-placeholder">正在描图并提取主色...</div>';

  const formData = new FormData();
  formData.append('image', traceFile.files[0]);
  formData.append('mode', document.getElementById('traceMode').value);
  formData.append('filter_speckle', filterSpeckle.value);
  formData.append('path_precision', pathPrecision.value);
  formData.append('ignore_white', document.getElementById('ignoreWhite').checked ? '1' : '0');

  try {
    const resp = await apiFetch('/api/trace/colors', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!data.success) {
      paletteResults.innerHTML = `<div class="match-placeholder" style="color:var(--error)">错误: ${escapeHtml(data.error)}</div>`;
      return;
    }

    if (!data.palette || data.palette.length === 0) {
      paletteResults.innerHTML = '<div class="match-placeholder">未检测到可识别的主色（可能为单色或渐变图）</div>';
      return;
    }

    let html = '<div class="palette-title">检测到 ' + data.palette.length + ' 个主色 · Pantone 色卡</div>';

    data.palette.forEach((item, idx) => {
      const c = item.color;
      const top = item.pantone_matches[0] || null;
      const pct = Math.round((c.share || 0) * 100);
      const rgb = (c.rgb || []).join(',');

      html += `<div class="swatch-card">
        <div class="swatch-large" style="background:${escapeHtml(c.hex)}"></div>
        <div class="swatch-body">
          <div class="swatch-head">
            <span class="swatch-hex">${escapeHtml(c.hex)}</span>
            <span class="swatch-share">${pct}%</span>
          </div>
          ${top
            ? `<div class="swatch-pantone">${escapeHtml(top.name)}
                 <span class="match-de ${gradeClass(top.delta_e)}">ΔE ${escapeHtml(top.delta_e)}</span>
               </div>
               <div class="swatch-values">
                 <span>HEX ${escapeHtml(c.hex)}</span>
                 <span>CMYK ${escapeHtml(top.cmyk.join('/'))}</span>
                 <span>RGB ${escapeHtml(rgb)}</span>
               </div>
               ${item.pantone_matches.length > 1 ? `<button class="btn btn-small swatch-expand" data-i="${idx}">全部匹配 (${item.pantone_matches.length})</button>` : ''}`
            : `<div class="swatch-pantone">无匹配色</div>`}
          <div class="swatch-more hidden" data-more="${idx}">
            ${(item.pantone_matches || []).slice(1).map(m =>
              `<div class="swatch-more-row">${escapeHtml(m.name)} · ${escapeHtml(m.hex)}
                 <span class="match-de ${gradeClass(m.delta_e)}">ΔE ${escapeHtml(m.delta_e)}</span></div>`).join('')}
          </div>
        </div>
      </div>`;
    });
    paletteResults.innerHTML = html;

    // 展开/收起 top-3 匹配
    paletteResults.querySelectorAll('.swatch-expand').forEach(btn => {
      btn.addEventListener('click', () => {
        const more = paletteResults.querySelector(`[data-more="${btn.dataset.i}"]`);
        more.classList.toggle('hidden');
        btn.textContent = more.classList.contains('hidden')
          ? `全部匹配 (${data.palette[Number(btn.dataset.i)].pantone_matches.length})` : '收起';
      });
    });
  } catch (e) {
    paletteResults.innerHTML = `<div class="match-placeholder" style="color:var(--error)">请求失败: ${escapeHtml(e)}</div>`;
  } finally {
    colorMatchBtn.disabled = false;
    colorMatchBtn.textContent = '提取主色 & Pantone 匹配';
  }
});

// === Pantone Lookup ===
const pantoneInput = document.getElementById('pantoneInput');
const pantoneBtn = document.getElementById('pantoneBtn');
const pantoneResult = document.getElementById('pantoneResult');
const pantoneError = document.getElementById('pantoneError');

pantoneBtn.addEventListener('click', async () => {
  const name = pantoneInput.value.trim();
  if (!name) return;
  pantoneResult.classList.add('hidden');
  pantoneError.classList.add('hidden');

  try {
    const resp = await apiFetch(`/api/pantone/lookup?name=${encodeURIComponent(name)}`);
    const data = await resp.json();
    if (data.success) {
      const r = data.result;
      document.getElementById('pantoneSwatch').style.background = r.hex;
      document.getElementById('pantoneName').textContent = r.name;
      document.getElementById('pantoneHex').textContent = r.hex;
      document.getElementById('pantoneCmyk').textContent = `${r.c}/${r.m}/${r.y}/${r.k}`;
      document.getElementById('pantoneRgb').textContent = r.rgb || 'N/A';
      pantoneResult.classList.remove('hidden');
    } else {
      pantoneError.textContent = data.error || '查询失败';
      pantoneError.classList.remove('hidden');
    }
  } catch (e) {
    pantoneError.textContent = '请求失败: ' + e;
    pantoneError.classList.remove('hidden');
  }
});

pantoneInput.addEventListener('keydown', e => { if (e.key === 'Enter') pantoneBtn.click(); });

// === Color Match ===
const colorPicker = document.getElementById('colorPicker');
const hexInput = document.getElementById('hexInput');
const matchBtn = document.getElementById('matchBtn');
const matchResults = document.getElementById('matchResults');

colorPicker.addEventListener('input', () => { hexInput.value = colorPicker.value; });
hexInput.addEventListener('input', () => {
  if (hexInput.value.startsWith('#') && hexInput.value.length === 7) {
    colorPicker.value = hexInput.value;
  }
});

matchBtn.addEventListener('click', async () => {
  let hex = hexInput.value.trim();
  if (!hex.startsWith('#')) hex = '#' + hex;
  if (hex.length !== 7) return;

  matchResults.innerHTML = '<div class="match-placeholder">查询中...</div>';

  try {
    const resp = await apiFetch('/api/pantone/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hex_color: hex }),
    });
    const data = await resp.json();
    if (data.success && data.matches.length > 0) {
      matchResults.innerHTML = '';
      data.matches.forEach(m => {
        const gradeClass = m.delta_e < 1 ? 'excellent' : m.delta_e < 3 ? 'good' : m.delta_e < 6 ? 'fair' : 'poor';
        matchResults.innerHTML += `
          <div class="match-item">
            <div class="match-swatch" style="background:${escapeHtml(m.hex)}"></div>
            <div class="match-info">
              <div class="match-name">${escapeHtml(m.name)}</div>
              <div class="match-hex">${escapeHtml(m.hex)} · CMYK ${escapeHtml(m.cmyk.join('/'))}</div>
            </div>
            <div class="match-de ${gradeClass}">ΔE ${escapeHtml(m.delta_e)}</div>
          </div>
        `;
      });
    } else {
      matchResults.innerHTML = '<div class="match-placeholder">未找到匹配颜色</div>';
    }
  } catch (e) {
    matchResults.innerHTML = `<div class="match-placeholder" style="color:var(--error)">请求失败: ${e}</div>`;
  }
});

// === Print Cost ===
// Initial color match load
matchBtn.click();
