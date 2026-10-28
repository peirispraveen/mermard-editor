#!/usr/bin/env python3
"""Local Mermaid editor with live preview and PNG/PDF/SVG export.

Install:  python -m pip install -r requirements.txt
Run:      python mermaid_studio.py
"""

from __future__ import annotations

import threading
import webbrowser

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mermaid Studio</title>
<style>
  :root { color-scheme: light; --ink:#182230; --muted:#687386; --line:#dce3eb; --panel:#fff; --surface:#f5f8fb; --accent:#245d72; --accent2:#e3f0f3; }
  * { box-sizing:border-box; }
  body { margin:0; color:var(--ink); font-family:Inter,Segoe UI,Arial,sans-serif; background:#f3f6f9; }
  button,select,input,textarea { font:inherit; }
  button { border:1px solid #cbd5df; border-radius:8px; padding:8px 11px; background:#fff; color:var(--ink); cursor:pointer; white-space:nowrap; }
  button:hover { background:#edf4f6; border-color:#9cb5c0; }
  button.primary { background:var(--accent); color:white; border-color:var(--accent); }
  button.primary:hover { background:#19485a; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  .app-header { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 16px; background:white; border-bottom:1px solid var(--line); }
  .brand { display:flex; align-items:center; gap:11px; min-width:210px; }
  .brand-mark { width:36px;height:36px;border-radius:10px;background:var(--accent2);display:grid;place-items:center;color:var(--accent);font-size:19px;font-weight:800; }
  .brand h1 { font-size:17px; margin:0; font-weight:700; }
  .brand p { font-size:11px; margin:3px 0 0; color:var(--muted); }
  .header-actions { display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:8px; }
  .filename { width:180px; padding:8px 10px; border:1px solid var(--line); border-radius:8px; }
  .theme-select { padding:8px 9px; border:1px solid var(--line); border-radius:8px; background:white; }
  .workspace { display:grid; grid-template-columns:minmax(330px, 43%) minmax(0, 57%); gap:12px; height:calc(100vh - 66px); padding:12px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden; min-width:0; min-height:0; display:flex; flex-direction:column; box-shadow:0 2px 6px #18223008; }
  .panel-header { min-height:48px; display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px 13px; border-bottom:1px solid var(--line); }
  .panel-title { font-size:13px; font-weight:700; letter-spacing:.02em; display:flex; align-items:center; gap:8px; }
  .kicker { font-size:11px; color:var(--muted); font-weight:500; }
  .auto-update { font-size:12px; color:var(--muted); display:flex; align-items:center; gap:6px; white-space:nowrap; }
  #source { width:100%; flex:1; resize:none; border:0; outline:none; padding:15px 15px 22px; color:#172c3c; background:#fff; font:13px/1.62 Consolas,Monaco,'Courier New',monospace; tab-size:2; white-space:pre; overflow:auto; }
  .editor-footer { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:9px 12px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; }
  .editor-footer button { padding:6px 9px; font-size:11px; }
  .preview-toolbar { display:flex; align-items:center; flex-wrap:wrap; gap:6px; }
  .preview-toolbar button { font-size:11px; padding:6px 9px; }
  .stage { flex:1; min-height:0; overflow:auto; padding:18px; position:relative; background-color:#fbfdfe; background-image:radial-gradient(#dbe8ee 1.05px,transparent 1.05px); background-size:22px 22px; }
  #diagramMount { min-width:100%; width:max-content; min-height:100%; display:flex; align-items:flex-start; justify-content:center; }
  #diagramMount svg { display:block; width:auto; height:auto; max-width:none !important; overflow:visible; }
  #diagramMount .node { cursor:pointer; }
  #diagramMount .node:hover { filter:drop-shadow(0 0 2px #245d7255); }
  .hint { padding:9px 13px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; line-height:1.5; }
  #renderStatus { display:flex; align-items:center; gap:7px; font-size:11px; color:var(--muted); min-width:0; }
  .dot { width:7px;height:7px;border-radius:50%;background:#2b9b70;flex-shrink:0; }
  #errorBox { display:none; white-space:pre-wrap; color:#9e2b27; background:#fff3f1; border:1px solid #f3c7c2; border-radius:8px; padding:10px; margin:0 0 12px; font:12px/1.5 Consolas,monospace; }
  .empty { color:#748293; font-size:14px; text-align:center; margin:auto; padding:28px; max-width:520px; }
  .subtle { color:var(--muted); font-size:11px; }
  @media(max-width:900px) {
    .app-header { align-items:flex-start; flex-direction:column; }
    .header-actions { justify-content:flex-start; }
    .workspace { grid-template-columns:1fr; height:auto; min-height:calc(100vh - 120px); }
    .panel { min-height:480px; }
    #source { min-height:390px; }
    .stage { min-height:420px; }
  }
  @media(max-width:520px) { .filename { width:145px; } .brand { min-width:0; } .workspace { padding:7px; gap:8px; } .stage { padding:10px; } }
</style>
</head>
<body>
<header class="app-header">
  <div class="brand">
    <div class="brand-mark">M</div>
    <div><h1>Mermaid Studio</h1><p>Local editor · live preview · export</p></div>
  </div>
  <div class="header-actions">
    <input id="filename" class="filename" aria-label="Export filename" value="mermaid-diagram" title="Export filename">
    <select id="theme" class="theme-select" aria-label="Diagram theme" title="Diagram theme">
      <option value="default">Default theme</option><option value="neutral">Neutral theme</option><option value="forest">Forest theme</option><option value="dark">Dark theme</option>
    </select>
    <button id="downloadMmd">Save .mmd</button>
    <button id="downloadSvg">SVG</button>
    <button id="downloadPng" class="primary">PNG · 300 DPI</button>
    <button id="downloadPdf">PDF / Print</button>
  </div>
</header>
<main class="workspace">
  <section class="panel">
    <div class="panel-header">
      <div class="panel-title"><span>〈/〉</span> Mermaid Code <span class="kicker" id="lineCount">0 lines</span></div>
      <label class="auto-update"><input id="autoUpdate" type="checkbox" checked> Auto-update</label>
    </div>
    <textarea id="source" spellcheck="false" aria-label="Mermaid code editor">flowchart TD
    A[Paste Mermaid code here] --> B[Edit the code]
    B --> C{Preview looks right?}
    C -- Yes --> D[Export PNG or PDF]
    C -- Not yet --> B</textarea>
    <div class="editor-footer">
      <span>Ctrl + Enter to render · edits update the preview automatically</span>
      <span style="display:flex;gap:6px"><button id="renderNow">Render</button><button id="copyCode">Copy code</button></span>
    </div>
  </section>
  <section class="panel">
    <div class="panel-header">
      <div class="panel-title">Diagram Preview</div>
      <div class="preview-toolbar">
        <span id="renderStatus"><span class="dot"></span><span>Loading Mermaid…</span></span>
        <button id="fitView" title="Fit diagram to the preview">Fit</button>
      </div>
    </div>
    <div class="stage" id="stage">
      <div id="errorBox"></div>
      <div id="diagramMount"><div class="empty">Your Mermaid diagram will appear here.</div></div>
    </div>
    <div class="hint">Tip: for common flowcharts, click a node in the preview to edit its label. The edit is written back into the code. Other Mermaid diagram types can always be changed in the code editor.</div>
  </section>
</main>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@12.2.0/dist/mermaid.esm.min.mjs';

const editor = document.getElementById('source');
const mount = document.getElementById('diagramMount');
const stage = document.getElementById('stage');
const errorBox = document.getElementById('errorBox');
const status = document.getElementById('renderStatus');
const themeSelect = document.getElementById('theme');
const autoUpdate = document.getElementById('autoUpdate');
let debounceTimer = null;
let renderVersion = 0;
let renderCounter = 0;

function setStatus(message, isError=false) {
  status.replaceChildren();
  const dot = document.createElement('span');
  dot.className = 'dot';
  dot.style.background = isError ? '#c74440' : '#2b9b70';
  const text = document.createElement('span');
  text.textContent = message;
  status.append(dot, text);
}
function updateLineCount() {
  const count = editor.value.length ? editor.value.split(/\r?\n/).length : 0;
  document.getElementById('lineCount').textContent = `${count} line${count === 1 ? '' : 's'}`;
}
function initMermaid() {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: themeSelect.value,
    flowchart: { htmlLabels: true, curve: 'basis', useMaxWidth: false },
    sequence: { useMaxWidth: true },
    gantt: { useMaxWidth: true }
  });
}
async function renderDiagram() {
  const source = editor.value.trim();
  const thisVersion = ++renderVersion;
  if (!source) {
    mount.innerHTML = '<div class="empty">Paste Mermaid code into the editor to render a diagram.</div>';
    errorBox.style.display = 'none';
    setStatus('Waiting for code');
    return;
  }
  initMermaid();
  setStatus('Rendering…');
  try {
    const id = `mermaid-diagram-${++renderCounter}`;
    const result = await mermaid.render(id, source);
    if (thisVersion !== renderVersion) return;
    mount.innerHTML = result.svg;
    if (result.bindFunctions) result.bindFunctions(mount);
    errorBox.style.display = 'none';
    attachNodeEditors();
    setStatus('Rendered · click a flowchart node to edit');
  } catch (error) {
    if (thisVersion !== renderVersion) return;
    errorBox.textContent = String(error?.message || error).replace(/^Error:\s*/, '');
    errorBox.style.display = 'block';
    mount.innerHTML = '<div class="empty">Could not render this code. Fix the Mermaid syntax, then try again.</div>';
    setStatus('Render error', true);
  }
}
function scheduleRender() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(renderDiagram, 280);
}
function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
function replaceNodeLabel(code, nodeId, newLabel) {
  const id = escapeRegExp(nodeId);
  const pairs = [['([', '])'], ['[(', ')]'], ['((', '))'], ['{{', '}}'], ['[[', ']]'], ['[/', '/]'], ['[\\', '\\]'], ['[', ']'], ['(', ')'], ['{', '}'], ['>', ']']];
  for (const [open, close] of pairs) {
    const re = new RegExp(`(^|[\\s;])(${id})\\s*${escapeRegExp(open)}([\\s\\S]*?)${escapeRegExp(close)}`, 'm');
    const match = code.match(re);
    if (!match) continue;
    const oldLabel = match[3];
    let replacementLabel = newLabel;
    if (oldLabel.length >= 2 && ['"', "'", '`'].includes(oldLabel[0]) && oldLabel.at(-1) === oldLabel[0]) {
      replacementLabel = oldLabel[0] + newLabel + oldLabel[0];
    }
    return { code: code.replace(re, (_whole, prefix, matchedId) => `${prefix}${matchedId}${open}${replacementLabel}${close}`), found: true };
  }
  return { code, found: false };
}
function attachNodeEditors() {
  mount.querySelectorAll('g.node').forEach(node => {
    node.title = 'Click to edit this flowchart node label';
    node.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      const visible = node.querySelector('.nodeLabel')?.innerText || node.textContent || '';
      const nodeId = node.getAttribute('data-id') || (node.id || '').replace(/^flowchart-/, '').replace(/-\d+$/, '');
      if (!nodeId) return;
      const value = window.prompt(`Edit label for node “${nodeId}” (single line):`, visible.trim());
      if (value === null) return;
      const replacement = replaceNodeLabel(editor.value, nodeId, value.replace(/[\r\n]+/g, ' ').trim());
      if (!replacement.found) {
        window.alert('This node label could not be matched to a simple flowchart declaration. Edit the label directly in the code panel instead.');
        return;
      }
      editor.value = replacement.code;
      updateLineCount();
      renderDiagram();
    });
  });
}
function safeFilename(extension) {
  let base = document.getElementById('filename').value.trim() || 'mermaid-diagram';
  base = base.replace(/[<>:"/\\|?*\x00-\x1F]/g, '-').replace(/[. ]+$/g, '').slice(0, 100) || 'mermaid-diagram';
  return base.toLowerCase().endsWith(`.${extension}`) ? base : `${base}.${extension}`;
}
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
function svgForExport() {
  const current = mount.querySelector('svg');
  if (!current) throw new Error('Render a valid diagram before exporting.');
  const svg = current.cloneNode(true);
  const viewBox = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
  const width = viewBox.length === 4 && viewBox[2] > 0 ? viewBox[2] : parseFloat(svg.getAttribute('width')) || current.getBoundingClientRect().width;
  const height = viewBox.length === 4 && viewBox[3] > 0 ? viewBox[3] : parseFloat(svg.getAttribute('height')) || current.getBoundingClientRect().height;
  if (!(width > 0 && height > 0)) throw new Error('Could not determine the diagram dimensions.');
  svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  svg.setAttribute('width', `${width}px`);
  svg.setAttribute('height', `${height}px`);
  svg.style.width = `${width}px`;
  svg.style.height = `${height}px`;
  svg.style.maxWidth = 'none';
  const svgString = new XMLSerializer().serializeToString(svg);
  return { svg, svgString, width, height };
}
async function addPngDpi(blob, dpi=300) {
  const png = new Uint8Array(await blob.arrayBuffer());
  // PNG pHYs stores pixels per metre; insert it just after the 33-byte IHDR chunk.
  if (png.length < 33 || png[0] !== 137 || png[1] !== 80) return blob;
  const phys = new Uint8Array(21);
  const view = new DataView(phys.buffer);
  view.setUint32(0, 9, false);
  phys.set(new TextEncoder().encode('pHYs'), 4);
  const pixelsPerMetre = Math.round(dpi / 0.0254);
  view.setUint32(8, pixelsPerMetre, false);
  view.setUint32(12, pixelsPerMetre, false);
  phys[16] = 1;
  const crc = crc32(phys.subarray(4, 17));
  view.setUint32(17, crc, false);
  const output = new Uint8Array(png.length + phys.length);
  output.set(png.subarray(0, 33), 0);
  output.set(phys, 33);
  output.set(png.subarray(33), 33 + phys.length);
  return new Blob([output], { type: 'image/png' });
}
function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
async function exportPng() {
  try {
    const { svgString, width, height } = svgForExport();
    const scale = 300 / 96;
    const outWidth = Math.ceil(width * scale), outHeight = Math.ceil(height * scale);
    if (outWidth > 30000 || outHeight > 30000 || outWidth * outHeight > 180000000) {
      throw new Error('This diagram is too large for a browser canvas at 300 DPI. Try reducing the diagram size or exporting as PDF/SVG.');
    }
    setStatus('Preparing 300-DPI PNG…');
    const sourceUrl = URL.createObjectURL(new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' }));
    const image = new Image();
    image.onload = async () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = outWidth; canvas.height = outHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error('Could not create export canvas.');
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, outWidth, outHeight);
        ctx.drawImage(image, 0, 0, outWidth, outHeight);
        const canvasBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        if (!canvasBlob) throw new Error('PNG encoding failed.');
        const finalBlob = await addPngDpi(canvasBlob, 300);
        downloadBlob(finalBlob, safeFilename('png'));
        setStatus(`PNG exported · ${outWidth} × ${outHeight}px · 300 DPI`);
      } catch (error) {
        window.alert(error.message || String(error)); setStatus('PNG export failed', true);
      } finally { URL.revokeObjectURL(sourceUrl); }
    };
    image.onerror = () => { URL.revokeObjectURL(sourceUrl); window.alert('The diagram could not be rasterized. Try SVG or PDF export.'); setStatus('PNG export failed', true); };
    image.src = sourceUrl;
  } catch (error) { window.alert(error.message || String(error)); setStatus('PNG export failed', true); }
}
function exportSvg() {
  try {
    const { svgString } = svgForExport();
    downloadBlob(new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' }), safeFilename('svg'));
    setStatus('SVG exported · scalable vector');
  } catch (error) { window.alert(error.message || String(error)); }
}
function exportPdf() {
  let data;
  try { data = svgForExport(); } catch (error) { window.alert(error.message || String(error)); return; }
  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    window.alert('The print window was blocked. Allow pop-ups for this local page, then try again.');
    return;
  }
  const orientation = data.width >= data.height ? 'landscape' : 'portrait';
  printWindow.document.open();
  printWindow.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${safeFilename('pdf')}</title><style>
    @page { size: ${orientation}; margin: 8mm; }
    * { box-sizing:border-box; } html,body { margin:0; width:100%; height:100%; }
    body { display:flex; align-items:center; justify-content:center; print-color-adjust:exact; -webkit-print-color-adjust:exact; }
    #page { width:100%; height:calc(100vh - 16mm); display:flex; align-items:center; justify-content:center; overflow:hidden; }
    svg { display:block; width:auto !important; height:auto !important; max-width:100% !important; max-height:100% !important; }
    @media screen { body { background:#edf1f5; padding:16px; } #page { background:white; box-shadow:0 2px 14px #0002; } }
  </style></head><body><div id="page"></div></body></html>`);
  printWindow.document.close();
  const copiedSvg = printWindow.document.importNode(data.svg, true);
  printWindow.document.getElementById('page').appendChild(copiedSvg);
  setTimeout(() => { printWindow.focus(); printWindow.print(); }, 800);
  setStatus('PDF opened · choose “Save as PDF” in the print dialog');
}

editor.addEventListener('input', () => { updateLineCount(); if (autoUpdate.checked) scheduleRender(); });
document.getElementById('renderNow').addEventListener('click', renderDiagram);
document.getElementById('copyCode').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(editor.value); setStatus('Code copied to clipboard'); }
  catch { editor.select(); document.execCommand('copy'); setStatus('Code copied to clipboard'); }
});
document.getElementById('downloadMmd').addEventListener('click', () => downloadBlob(new Blob([editor.value], {type:'text/plain;charset=utf-8'}), safeFilename('mmd')));
document.getElementById('downloadSvg').addEventListener('click', exportSvg);
document.getElementById('downloadPng').addEventListener('click', exportPng);
document.getElementById('downloadPdf').addEventListener('click', exportPdf);
document.getElementById('fitView').addEventListener('click', () => {
  const svg = mount.querySelector('svg');
  if (!svg) return;
  const box = svg.getBoundingClientRect();
  const availableWidth = stage.clientWidth - 36;
  const availableHeight = stage.clientHeight - 36;
  const scale = Math.min(availableWidth / box.width, availableHeight / box.height, 1);
  svg.style.width = `${Math.max(1, box.width * scale)}px`;
  svg.style.height = `${Math.max(1, box.height * scale)}px`;
  setStatus(`Fit preview · ${Math.round(scale * 100)}%`);
});
themeSelect.addEventListener('change', renderDiagram);
editor.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); renderDiagram(); } });
updateLineCount();
renderDiagram();
</script>
</body>
</html>'''


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path != "/":
            self.send_error(404, "Not found")
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # Keep the terminal output tidy while serving this local-only app.
        return


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), RequestHandler)
    url = f"http://{host}:{port}"
    print("Mermaid Studio is starting locally (no Python packages required).")
    print(f"Open this address in your browser: {url}")
    print("Keep this terminal open while using the app; press Ctrl+C to stop it.")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nMermaid Studio stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
