#!/usr/bin/env python3
"""Mermaid Studio: paste Mermaid code, see a live diagram, click elements to edit,
and export a 300 DPI PNG or PDF to ./exports."""
import io, json, re, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from PIL import Image

HOST, PORT = "127.0.0.1", 8765
OUT = Path("exports"); OUT.mkdir(exist_ok=True)
DPI = 300

HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>Mermaid Studio</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/lib/codemirror.css">
<script src="https://cdn.jsdelivr.net/npm/codemirror@5.65.16/lib/codemirror.js"></script>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Arial,sans-serif;height:100vh;display:flex;flex-direction:column;background:#f4f7f8}
#bar{display:flex;gap:8px;align-items:center;padding:8px 12px;background:#dfeef0;flex-wrap:wrap}
#bar button,#bar select{padding:6px 10px;border:1px solid #9bb;border-radius:6px;background:#fff;cursor:pointer}
#bar button:hover{background:#eef}.sp{flex:1}
#main{flex:1;display:flex;min-height:0}
#left{width:42%;min-width:260px;display:flex;flex-direction:column;border-right:2px solid #bcd;resize:horizontal;overflow:auto}
.CodeMirror{flex:1;height:100%;font-family:Consolas,monospace;font-size:14px}
#err{color:#b00020;background:#fff0f0;padding:6px 10px;font:12px monospace;white-space:pre-wrap;display:none;max-height:120px;overflow:auto}
#right{flex:1;position:relative;overflow:hidden;background-image:radial-gradient(#cdd 1px,transparent 1px);background-size:24px 24px}
#stage{position:absolute;left:0;top:0;transform-origin:0 0;cursor:grab}
#stage svg{max-width:none!important;display:block}
g.node,g.cluster,g.edgeLabel,.edgeLabel{cursor:pointer}
g.node:hover rect,g.node:hover polygon,g.node:hover circle,g.node:hover path{stroke:#e91e63!important;stroke-width:3px!important}
.sel rect,.sel polygon,.sel circle,.sel path{stroke:#e91e63!important;stroke-width:3px!important}
#panel{position:absolute;right:12px;top:12px;width:270px;background:#fff;border:1px solid #9bb;border-radius:8px;padding:10px;box-shadow:0 4px 14px #0003;display:none;font-size:13px}
#panel label{display:block;margin-top:6px}#panel textarea{width:100%;height:70px}
#panel input[type=color]{vertical-align:middle}
#toast{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);background:#222;color:#fff;padding:8px 14px;border-radius:6px;display:none;z-index:9}
</style></head><body>
<div id="bar">
 <b>Mermaid Studio</b>
 <label><input type="checkbox" id="auto" checked> Auto-update</label>
 <button id="render">Render</button>
 <select id="theme"><option>default</option><option>neutral</option><option>forest</option><option>dark</option><option>base</option></select>
 <select id="dir"><option value="">Direction</option><option>TB</option><option>LR</option><option>BT</option><option>RL</option></select>
 <button id="fit">Fit</button><button id="z1">100%</button>
 <span class="sp"></span>
 <button id="png">Save PNG (300 DPI)</button>
 <button id="pdf">Save PDF (300 DPI)</button>
 <button id="mmd">Save .mmd</button>
</div>
<div id="main">
 <div id="left"><textarea id="code"></textarea><div id="err"></div></div>
 <div id="right"><div id="stage"></div>
  <div id="panel">
   <b id="ptitle">Edit element</b>
   <label>Label<textarea id="plabel"></textarea></label>
   <div id="styles">
    <label>Fill <input type="color" id="pfill" value="#ffffff"></label>
    <label>Border <input type="color" id="pstroke" value="#333333"></label>
    <label>Text <input type="color" id="pcolor" value="#000000"></label>
    <label>Border width <input type="number" id="pw" value="1" min="0" max="10" style="width:60px"></label>
   </div>
   <div style="margin-top:8px"><button id="papply">Apply</button> <button id="pclose">Close</button></div>
  </div>
 </div></div>
<div id="toast"></div>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const $=id=>document.getElementById(id);
const SAMPLE=`flowchart TB
    DEV["DEV API layer"] --> MAIN["DS Core: FastAPI app<br/>routes the request"]
    subgraph NEW["POST /post-new-invoice (no template yet)"]
        direction TB
        N1["PDF to image<br/>page 1, 300 DPI"] --> N2["Record image dimension"] --> N3["LLM call 1: header fields"] --> N4["OCR full page"]
    end
    subgraph EXT["POST /post-ext-invoice (template supplied)"]
        direction TB
        E1["PDF to image"] --> E2["Resize to template"] --> E3{"Anchor found?"}
        E3 -->|yes| E4["Shift box"]
        E3 -->|no| E5["Use template box"]
    end
    MAIN --> NEW
    MAIN --> EXT
    style N1 fill:#dbeafe,stroke:#2563eb`;
const cm=CodeMirror.fromTextArea($('code'),{lineNumbers:true,lineWrapping:false,value:SAMPLE});
cm.setValue(localStorage.getItem('mm_code')||SAMPLE);
let seq=0,tx=0,ty=0,sc=1,sel=null,selKind=null;

function cfg(){mermaid.initialize({startOnLoad:false,theme:$('theme').value,securityLevel:'loose',
  flowchart:{htmlLabels:false,useMaxWidth:false},htmlLabels:false,maxTextSize:500000,maxEdges:5000});}
cfg();
function toast(t,ms=3500){const e=$('toast');e.textContent=t;e.style.display='block';clearTimeout(e._t);e._t=setTimeout(()=>e.style.display='none',ms);}

async function render(keepView=false){
  const code=cm.getValue(); localStorage.setItem('mm_code',code);
  try{
    await mermaid.parse(code);
    const {svg}=await mermaid.render('mm'+(++seq),code);
    $('stage').innerHTML=svg; $('err').style.display='none';
    document.querySelectorAll('[id^=dmm]').forEach(e=>e.remove());
    attach(); if(!keepView) fit();
  }catch(e){$('err').textContent=String(e.message||e);$('err').style.display='block';
    document.querySelectorAll('[id^=dmm]').forEach(e=>e.remove());}
}
function applyView(){$('stage').style.transform=`translate(${tx}px,${ty}px) scale(${sc})`;}
function svgSize(){const s=$('stage').querySelector('svg');if(!s)return[1,1];
  const vb=s.viewBox.baseVal;return vb&&vb.width?[vb.width,vb.height]:[s.getBBox().width,s.getBBox().height];}
function fit(){const [w,h]=svgSize();const r=$('right');
  sc=Math.min((r.clientWidth-40)/w,(r.clientHeight-40)/h,2);tx=(r.clientWidth-w*sc)/2;ty=(r.clientHeight-h*sc)/2;
  const s=$('stage').querySelector('svg');if(s){s.setAttribute('width',w);s.setAttribute('height',h);}applyView();}
$('fit').onclick=fit;$('z1').onclick=()=>{sc=1;applyView();};

// pan + zoom
const R=$('right');let drag=null,moved=0;
R.addEventListener('wheel',e=>{e.preventDefault();const b=R.getBoundingClientRect();const x=e.clientX-b.left,y=e.clientY-b.top;
  const k=e.deltaY<0?1.12:1/1.12;tx=x-(x-tx)*k;ty=y-(y-ty)*k;sc*=k;applyView();},{passive:false});
R.addEventListener('mousedown',e=>{if(e.target.closest('#panel'))return;drag={x:e.clientX-tx,y:e.clientY-ty};moved=0;});
window.addEventListener('mousemove',e=>{if(!drag)return;moved++;tx=e.clientX-drag.x;ty=e.clientY-drag.y;applyView();});
window.addEventListener('mouseup',()=>drag=null);

// element editing
const esc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
const OPEN='(?:\\[\\[|\\[\\(|\\(\\(|\\(\\[|\\{\\{|\\[\\/|\\[\\\\|\\[|\\(|\\{|>)';
function nodeRe(id){return new RegExp('(\\b'+esc(id)+'\\s*'+OPEN+'\\s*)("(?:[^"]*)"|[^\\]\\)\\}"\\n]*)');}
function getNodeLabel(id){const m=cm.getValue().match(nodeRe(id));
  return m?m[2].replace(/^"|"$/g,'').replace(/<br\s*\/?>/gi,'\n'):id;}
function setNodeLabel(code,id,txt){const t=txt.replace(/"/g,'#quot;').replace(/\n/g,'<br/>');
  if(nodeRe(id).test(code))return code.replace(nodeRe(id),(m,a)=>a+'"'+t+'"');
  return code;}
function subRe(id){return new RegExp('(\\bsubgraph\\s+'+esc(id)+'\\s*\\[)("[^"]*"|[^\\]\\n]*)');}
function setStyle(code,id,st){const line='    style '+id+' '+st;const re=new RegExp('^\\s*style\\s+'+esc(id)+'\\s.*$','m');
  return re.test(code)?code.replace(re,line):code.replace(/\s*$/,'\n')+line+'\n';}
function attach(){
  const svg=$('stage').querySelector('svg');
  svg.querySelectorAll('g.node').forEach(g=>{
    const m=g.id.match(/^(?:flowchart|graph)-(.+)-\d+$/)||g.id.match(/^(.+)$/);
    g.addEventListener('click',e=>{if(moved>4)return;e.stopPropagation();open('node',m[1],g);});});
  svg.querySelectorAll('g.cluster').forEach(g=>{
    g.addEventListener('click',e=>{if(moved>4)return;e.stopPropagation();open('cluster',g.id,g);});});
  svg.querySelectorAll('g.edgeLabel').forEach(g=>{
    g.addEventListener('click',e=>{if(moved>4)return;e.stopPropagation();open('edge',null,g);});});
}
function open(kind,id,g){
  document.querySelectorAll('.sel').forEach(x=>x.classList.remove('sel'));g.classList.add('sel');
  sel={id,g,orig:null};selKind=kind;const p=$('panel');p.style.display='block';
  $('ptitle').textContent=kind==='edge'?'Edit edge label':(kind==='cluster'?'Edit subgraph: ':'Edit node: ')+id;
  $('styles').style.display=kind==='edge'?'none':'block';
  let lab;
  if(kind==='node')lab=getNodeLabel(id);
  else if(kind==='cluster'){const m=cm.getValue().match(subRe(id));lab=m?m[2].replace(/^"|"$/g,''):id;}
  else lab=g.textContent.trim();
  sel.orig=lab;$('plabel').value=lab;}
$('pclose').onclick=()=>{$('panel').style.display='none';document.querySelectorAll('.sel').forEach(x=>x.classList.remove('sel'));};
$('papply').onclick=()=>{
  if(!sel)return;let code=cm.getValue();const nl=$('plabel').value;
  if(selKind==='node'){code=setNodeLabel(code,sel.id,nl);}
  else if(selKind==='cluster'){code=code.replace(subRe(sel.id),(m,a)=>a+'"'+nl+'"');}
  else{const o=sel.orig,n=nl.replace(/\n/g,'<br/>');
    const pats=[['|'+o+'|','|'+n+'|'],['-- '+o+' -->','-- '+n+' -->'],['-. '+o+' .->','-. '+n+' .->'],['== '+o+' ==>','== '+n+' ==>']];
    let ok=false;for(const [a,b] of pats){if(code.includes(a)){code=code.replace(a,b);ok=true;break;}}
    if(!ok)toast('Could not locate this edge label in the code; edit it in the code pane.');}
  if(selKind!=='edge'){
    const st=`fill:${$('pfill').value},stroke:${$('pstroke').value},color:${$('pcolor').value},stroke-width:${$('pw').value}px`;
    if(touched)code=setStyle(code,sel.id,st);}
  touched=false;cm.setValue(code);render(true);};
let touched=false;['pfill','pstroke','pcolor','pw'].forEach(i=>$(i).addEventListener('input',()=>touched=true));
R.addEventListener('click',e=>{if(e.target===R||e.target===$('stage'))$('pclose').click();});

// toolbar
let tm;cm.on('change',()=>{if(!$('auto').checked)return;clearTimeout(tm);tm=setTimeout(()=>render(true),450);});
$('render').onclick=()=>render(true);
$('theme').onchange=()=>{cfg();render(true);};
$('dir').onchange=()=>{const d=$('dir').value;if(!d)return;
  cm.setValue(cm.getValue().replace(/^(\s*(?:flowchart|graph))(\s+(?:TB|TD|BT|RL|LR))?/m,`$1 ${d}`));$('dir').value='';render();};

// export
function snapshot(){
  const s=$('stage').querySelector('svg').cloneNode(true);const [w,h]=svgSize();
  s.setAttribute('width',w);s.setAttribute('height',h);s.removeAttribute('style');
  s.setAttribute('xmlns','http://www.w3.org/2000/svg');
  const xml=new XMLSerializer().serializeToString(s);return {xml,w,h};}
async function rasterize(){
  const {xml,w,h}=snapshot();const want=300/96,MAX=16000;
  const k=Math.min(want,MAX/Math.max(w,h));
  const img=new Image();const url='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(xml);
  await new Promise((res,rej)=>{img.onload=res;img.onerror=()=>rej(new Error('SVG failed to load'));img.src=url;});
  const c=document.createElement('canvas');c.width=Math.round(w*k);c.height=Math.round(h*k);
  const x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,c.width,c.height);
  x.imageSmoothingQuality='high';x.drawImage(img,0,0,c.width,c.height);
  if(k<want)toast(`Large diagram: capped at ~${Math.round(k*96)} DPI to fit browser canvas limits`,6000);
  return new Promise(r=>c.toBlob(r,'image/png'));}
async function send(kind){
  try{if(!$('stage').querySelector('svg'))return toast('Nothing rendered yet');
    toast('Exporting…',60000);const b=await rasterize();
    const r=await fetch('/save?type='+kind,{method:'POST',body:b});const j=await r.json();
    toast(j.ok?'Saved: '+j.path+(j.note?' ('+j.note+')':''):'Error: '+j.error,7000);
  }catch(e){toast('Export failed: '+e.message,7000);}}
$('png').onclick=()=>send('png');$('pdf').onclick=()=>send('pdf');
$('mmd').onclick=async()=>{const r=await fetch('/save?type=mmd',{method:'POST',body:cm.getValue()});
  const j=await r.json();toast('Saved: '+j.path,5000);};
render();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path not in ("/", "/index.html"):
            self.send_error(404)
            return
        data = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/save":
            self.send_error(404)
            return
        kind = parse_qs(u.query).get("type", [""])[0]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        try:
            if kind == "png":
                img = Image.open(io.BytesIO(body))
                p = OUT / f"diagram_{stamp}.png"
                img.save(p, dpi=(DPI, DPI), optimize=True)
                note = f"{img.width}x{img.height}px @ {DPI} DPI"
            elif kind == "pdf":
                img = Image.open(io.BytesIO(body)).convert("RGB")
                p = OUT / f"diagram_{stamp}.pdf"
                img.save(p, "PDF", resolution=float(DPI), quality=100)
                note = f"{img.width}x{img.height}px @ {DPI} DPI"
            elif kind == "mmd":
                p = OUT / f"diagram_{stamp}.mmd"
                p.write_bytes(body)
                note = ""
            else:
                return self._json({"ok": False, "error": "bad type"}, 400)
            self._json({"ok": True, "path": str(p.resolve()), "note": note})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Mermaid Studio running at {url}  (exports -> {OUT.resolve()})  Ctrl+C to stop")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()