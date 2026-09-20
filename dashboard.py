"""Zero-dependency live dashboard (stdlib http.server). No Next.js needed."""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from agent import Agent
from config import settings
from database import Store

PAGE = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>tradagent 🤖📈</title>
<style>
body{font-family:Arial,Helvetica,sans-serif;background:#0b1220;color:#e5e7eb;margin:0;padding:24px}
.card{background:#111c33;border:1px solid #22345c;border-radius:14px;padding:18px;margin:12px 0}
.brand{display:flex;align-items:center;gap:14px}
button{background:#22c55e;border:0;color:#04120a;font-weight:700;padding:12px 22px;border-radius:10px;cursor:pointer;font-size:16px}
button:disabled{opacity:.5}.bar{height:12px;background:#1f2b4d;border-radius:8px;overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#22c55e,#38bdf8);width:0;transition:width .3s}
.sig{display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #22345c}
.BUY{color:#22c55e;font-weight:700}.SELL{color:#ef4444;font-weight:700}.HOLD{color:#facc15;font-weight:700}
small{color:#93a4c4}.foot{text-align:center}</style></head><body>
<div class=brand>
<svg width=52 height=52 viewBox="0 0 256 256"><rect x=8 y=8 width=240 height=240 rx=52 fill="#0b1220" stroke="#22c55e" stroke-width=10 /><line x1=78 y1=148 x2=78 y2=198 stroke="#ef4444" stroke-width=8 /><rect x=64 y=158 width=28 height=30 rx=4 fill="#ef4444"/><line x1=128 y1=114 x2=128 y2=174 stroke="#22c55e" stroke-width=8 /><rect x=114 y=124 width=28 height=38 rx=4 fill="#22c55e"/><line x1=178 y1=82 x2=178 y2=142 stroke="#22c55e" stroke-width=8 /><rect x=164 y=92 width=28 height=36 rx=4 fill="#22c55e"/><polyline points="50,204 102,164 132,180 188,104" fill=none stroke="#38bdf8" stroke-width=12 stroke-linecap=round stroke-linejoin=round /><polygon points="192,78 168,96 186,116" fill="#38bdf8"/></svg>
<h1>tradagent <small>fast local AI trading agent</small></h1>
</div>
<div class=card><button id=go onclick="run()">⚡ Generate trading signals</button>
<p id=st>Ready. Works with zero API keys — add Gemini/LunarCrush in .env for max accuracy.</p>
<div class=bar><i id=pb></i></div></div>
<div class=card><h3>📊 Signals</h3><div id=sigs><small>No signals yet — press the button.</small></div></div>
<div class="card foot"><small>tradagent v1.0 — Binance + CoinGecko + hybrid AI engine | cache refreshes every 5 min<br>© 2026 salim-slimani. All rights reserved.</small></div>
<script>
async function run(){go.disabled=true;st.textContent='⏳ Analyzing...';
 let r=await fetch('/api/run',{method:'POST'});let j=await r.json();
 if(j.signals&&j.signals.length){render(j.signals);pb.style.width='100%';st.textContent=(j.summary||'Done')+' ('+(j.duration_s||'?')+'s)';go.disabled=false;}
 else poll(j.job_id);}
async function poll(id){let r=await fetch('/api/job?id='+id);let j=await r.json();
 pb.style.width=j.progress+'%';st.textContent=j.step_message+' ('+j.progress+'%)';
 if(j.status!=='completed'){setTimeout(()=>poll(id),600);}else{load();go.disabled=false;}}
async function load(){let r=await fetch('/api/signals');render(await r.json());}
function render(s){
 sigs.innerHTML=s.map(x=>`<div class=sig><span><b>${x.symbol}</b> <small>${x.engine} | ${x.reasoning||''}</small></span><span class=${x.signal}>${x.signal} ${x.confidence}%</span></div>`).join('')||'<small>No results</small>';}
load();</script></body></html>"""


class H(BaseHTTPRequestHandler):
    store = Store(settings.db_path)

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/signals":
            return self._json(self.store.latest_signals())
        if u.path == "/api/job":
            j = self.store.job(parse_qs(u.query).get("id", [""])[0])
            return self._json(j or {"error": "not found"})
        html = PAGE.encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html))); self.end_headers(); self.wfile.write(html)

    def do_POST(self):
        if self.path == "/api/run":
            import threading
            before = time.time()
            threading.Thread(target=Agent().run, daemon=True).start()
            # wait until the worker creates its job row, then hand its id to the UI for polling
            jid = None
            for _ in range(40):
                time.sleep(0.15)
                cur = self.store.db.execute(
                    "SELECT id FROM analysis_jobs WHERE started_at>=? ORDER BY started_at DESC LIMIT 1",
                    (before,)).fetchone()
                if cur:
                    jid = cur[0]
                    break
            return self._json({"job_id": jid})
        return self._json({"error": "not found"}, 404)

    def log_message(self, *a): pass


def serve(port=8000):
    print(f"🤖 tradagent dashboard → http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), H).serve_forever()


if __name__ == "__main__":
    import sys
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
