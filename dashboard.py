"""Zero-dependency live dashboard (stdlib http.server). No Next.js needed."""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from agent import Agent
from config import settings
from database import Store

PAGE = """<!DOCTYPE html><html lang=ar dir=rtl><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>tradagent 🤖📈</title>
<style>
body{font-family:Tahoma,Arial;background:#0b1220;color:#e5e7eb;margin:0;padding:24px}
.card{background:#111c33;border:1px solid #22345c;border-radius:14px;padding:18px;margin:12px 0}
button{background:#22c55e;border:0;color:#04120a;font-weight:700;padding:12px 22px;border-radius:10px;cursor:pointer;font-size:16px}
button:disabled{opacity:.5}.bar{height:12px;background:#1f2b4d;border-radius:8px;overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#22c55e,#38bdf8);width:0;transition:width .3s}
.sig{display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #22345c}
.BUY{color:#22c55e;font-weight:700}.SELL{color:#ef4444;font-weight:700}.HOLD{color:#facc15;font-weight:700}
small{color:#93a4c4}</style></head><body>
<h1>🤖 tradagent <small>وكيل التداول الذكي — سريع ومتكامل</small></h1>
<div class=card><button id=go onclick="run()">⚡ توليد إشارات التداول</button>
<p id=st>جاهز. يعمل بدون مفاتيح API — أضف Gemini/LunarCrush في .env للدقة القصوى.</p>
<div class=bar><i id=pb></i></div></div>
<div class=card><h3>📊 الإشارات</h3><div id=sigs><small>لا توجد إشارات بعد — اضغط الزر.</small></div></div>
<div class=card><small>tradagent v1.0 — Binance + CoinGecko + محرك AI هجين | يتحدث كل 5 دقائق (كاش)</small></div>
<script>
async function run(){go.disabled=true;st.textContent='⏳ يحلل...';
 let r=await fetch('/api/run',{method:'POST'});let j=await r.json();
 poll(j.job_id);}
async function poll(id){let r=await fetch('/api/job?id='+id);let j=await r.json();
 pb.style.width=j.progress+'%';st.textContent=j.step_message+' ('+j.progress+'%)';
 if(j.status!=='completed'){setTimeout(()=>poll(id),600);}else{load();go.disabled=false;}}
async function load(){let r=await fetch('/api/signals');let s=await r.json();
 sigs.innerHTML=s.map(x=>`<div class=sig><span><b>${x.symbol}</b> <small>${x.engine} | ${x.reasoning||''}</small></span><span class=${x.signal}>${x.signal} ${x.confidence}%</span></div>`).join('')||'<small>لا نتائج</small>';}
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
