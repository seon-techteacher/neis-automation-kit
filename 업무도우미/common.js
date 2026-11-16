// 업무도우미 공통 도구 · © 2026 Kang SeongHo
// 설정은 이 브라우저의 localStorage에만 둔다. 도구에 넣은 파일과 명단은 저장하지 않는다.
'use strict';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const KEY = 'udesk.v3';

const Settings = {
  defaults: { youcallUrl: '', targetMB: 5, theme: 'system', field: '교과', phrases: [] },
  load() {
    let s = {};
    try { s = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch { /* 처음 상태로 */ }
    const out = { ...this.defaults, ...s };
    // 예전 판(0.1~0.2)에 넣어 둔 유콜 주소를 옮겨 온다.
    if (!out.youcallUrl) { try { out.youcallUrl = (JSON.parse(localStorage.getItem('udesk.v1') || '{}') || {}).youcallUrl || ''; } catch { /* 없음 */ } }
    return out;
  },
  save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { toast('설정을 저장하지 못했어요.'); } },
};
function applyTheme(theme, doc = document) {
  if (theme === 'light' || theme === 'dark') doc.documentElement.dataset.theme = theme;
  else delete doc.documentElement.dataset.theme;
}
applyTheme(Settings.load().theme);

let toastTimer;
function toast(msg) {
  let t = document.querySelector('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
}
async function copyText(text, okMsg = '복사했어요. 붙여 넣기(Ctrl+V) 하세요.') {
  try { await navigator.clipboard.writeText(text); toast(okMsg); }
  catch { toast('복사하지 못했어요. 글을 직접 선택해 복사해 주세요.'); }
}
function saveBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
const fmtMB = n => n >= 1048576 ? (n / 1048576).toFixed(1) + 'MB' : Math.max(1, Math.round(n / 1024)) + 'KB';
const baseName = n => n.replace(/\.[^.]+$/, '');
const extOf = n => (n.match(/\.([^.]+)$/) || ['', ''])[1].toLowerCase();

// 끌어다 놓기 + 눌러서 고르기
function dropZone(el, input, onFiles) {
  el.addEventListener('click', () => input.click());
  input.addEventListener('change', () => { const f = [...input.files]; input.value = ''; if (f.length) onFiles(f); });
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('over'); });
  el.addEventListener('dragleave', () => el.classList.remove('over'));
  el.addEventListener('drop', e => { e.preventDefault(); el.classList.remove('over'); const f = [...e.dataTransfer.files]; if (f.length) onFiles(f); });
}
// 탭: [data-tab] 버튼과 [data-pane] 구역
function tabs(bar, onChange) {
  bar.addEventListener('click', e => {
    const b = e.target.closest('button[data-tab]'); if (!b) return;
    bar.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    document.querySelectorAll('[data-pane]').forEach(p => p.hidden = p.dataset.pane !== b.dataset.tab);
    if (onChange) onChange(b.dataset.tab);
  });
  const want = location.hash.slice(1), first = bar.querySelector(`button[data-tab="${want}"]`);
  if (first) first.click();
}
// 엑셀에서 붙여 넣은 글을 표(줄 × 칸)로
const parseTable = text => text.replace(/\r/g, '').split('\n').filter(l => l.trim()).map(l => l.split('\t').map(c => c.trim()));
