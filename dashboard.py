"""Zero-dependency live dashboard (stdlib http.server). No frontend build step."""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from agent import Agent
from config import settings
from database import Store

LOGO_SVG = """<svg width=42 height=42 viewBox="0 0 256 256"><rect x=8 y=8 width=240 height=240 rx=52 fill="#0b1220" stroke="#22c55e" stroke-width=10 /><line x1=78 y1=148 x2=78 y2=198 stroke="#ef4444" stroke-width=8 /><rect x=64 y=158 width=28 height=30 rx=4 fill="#ef4444"/><line x1=128 y1=114 x2=128 y2=174 stroke="#22c55e" stroke-width=8 /><rect x=114 y=124 width=28 height=38 rx=4 fill="#22c55e"/><line x1=178 y1=82 x2=178 y2=142 stroke="#22c55e" stroke-width=8 /><rect x=164 y=92 width=28 height=36 rx=4 fill="#22c55e"/><polyline points="50,204 102,164 132,180 188,104" fill=none stroke="#38bdf8" stroke-width=12 stroke-linecap=round stroke-linejoin=round /><polygon points="192,78 168,96 186,116" fill="#38bdf8"/></svg>"""

PAGE = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<link rel=icon href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='22' fill='%230b1220'/><text x='50' y='70' font-size='58' text-anchor='middle' fill='%2322c55e' font-family='Arial' font-weight='bold'>T</text></svg>">
<title>tradagent — AI Trading Signals</title>
<style>
*{box-sizing:border-box}body{font-family:Inter,Arial,Helvetica,sans-serif;background:#0a0f1e;color:#e6ebf5;margin:0}
header{background:#0d1426;border-bottom:1px solid #1b2947;padding:14px 28px;position:sticky;top:0;z-index:5}
.hwrap{max-width:1400px;margin:0 auto;display:flex;justify-content:space-between;align-items:center}
.brand{display:flex;align-items:center;gap:12px}.brand b{font-size:20px}.brand small{display:block;color:#8b98b8;font-size:12px}
.live{text-align:right}.live b{font-size:14px}.live small{display:block;color:#8b98b8;font-size:12px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#22c55e;margin-left:8px;box-shadow:0 0 8px #22c55e}
main{max-width:1400px;margin:0 auto;padding:24px 28px;display:grid;grid-template-columns:320px 1fr;gap:20px}
.card{background:#111a30;border:1px solid #1e2a4a;border-radius:14px;padding:22px;margin-bottom:20px}
.card h2{margin:0 0 6px;font-size:19px}.lead{color:#9aa7c7;font-size:14px;line-height:1.55}
.how{background:#0d1528;border-radius:10px;padding:14px 16px;margin:14px 0;font-size:13px;color:#9aa7c7}
.how b{color:#e6ebf5}.how ol{margin:8px 0 0;padding-left:20px}.how li{margin:7px 0;line-height:1.5}
.how li::marker{font-weight:700}.how li:nth-child(1)::marker{color:#3b82f6}.how li:nth-child(2)::marker{color:#22c55e}.how li:nth-child(3)::marker{color:#8b5cf6}.how li:nth-child(4)::marker{color:#f59e0b}
.checks{display:grid;grid-template-columns:1fr 1fr;gap:8px 10px;margin:12px 0;font-size:13px}
.checks span{color:#c4cde3}.checks i{color:#22c55e;font-style:normal;margin-right:5px}
#go{width:100%;background:linear-gradient(90deg,#2563eb,#7c3aed);border:0;color:#fff;font-weight:700;padding:14px;border-radius:10px;cursor:pointer;font-size:15px;margin-top:6px}
#go:disabled{opacity:.55;cursor:wait}
.bar{height:8px;background:#1c2745;border-radius:6px;overflow:hidden;margin-top:12px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#22c55e,#38bdf8);width:0;transition:width .3s}
#st{font-size:12.5px;color:#8b98b8;margin:8px 0 0;min-height:18px}
.gloss dt{color:#7dd3fc;font-size:13px;margin-top:12px}.gloss dd{margin:3px 0 0;color:#9aa7c7;font-size:13px;line-height:1.5}
.hero{text-align:center;padding:34px 24px}
.hero h1{margin:0;font-size:27px}.hero p{color:#9aa7c7;font-size:14.5px}
.feats{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:22px;text-align:center}
.feats h3{font-size:15.5px;margin:12px 0 8px}.feats p{font-size:13px;line-height:1.6}
.tile{width:46px;height:46px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;font-size:21px}
.t-blue{background:#1b2c55}.t-purple{background:#2c1f56}.t-green{background:#123c2b}
.sec-h{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}.sec-h h2{margin:0;font-size:21px}
#sigsub{color:#8b98b8;font-size:13px;margin:4px 0 16px}
#sigs{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:18px}
.sigcard{background:#111a30;border:1px solid #1e2a4a;border-radius:14px;padding:20px}
.s-top{display:flex;align-items:center;gap:11px}
.badge{background:#1b2c55;color:#7dd3fc;font-weight:800;font-size:12.5px;border-radius:9px;padding:9px 10px;min-width:52px;text-align:center}
.s-top b{font-size:17px}.s-top small{display:block;color:#8b98b8;font-size:12px;font-weight:400}
.pill{margin-left:auto;font-weight:800;font-size:12.5px;border-radius:20px;padding:7px 15px;letter-spacing:.4px}
.pill.BUY{color:#22c55e;background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.4)}
.pill.SELL{color:#f87171;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.4)}
.pill.HOLD{color:#facc15;background:rgba(250,204,21,.1);border:1px solid rgba(250,204,21,.35)}
.conf{display:flex;justify-content:space-between;font-size:13px;color:#9aa7c7;margin:16px 0 7px}.conf b{color:#fff;font-size:15px}
.cbar{height:7px;background:#1c2745;border-radius:5px;overflow:hidden}.cbar>i{display:block;height:100%;border-radius:5px}
.cbar>i.BUY{background:#22c55e}.cbar>i.SELL{background:#ef4444}.cbar>i.HOLD{background:#eab308}
.tiles{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:14px}
.tiles2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.tilebox{background:#0d1528;border-radius:9px;padding:10px 12px;font-size:12px;color:#8b98b8}
.tilebox b{display:block;color:#fff;font-size:15px;margin-top:3px}
.mkt{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;font-size:13px;color:#c4cde3}
.up{color:#22c55e}.down{color:#f87171}
.analysis{background:#0d1528;border-radius:9px;padding:12px 14px;margin-top:12px;font-size:13px;color:#aeb9d4;line-height:1.65}
.analysis b{color:#e6ebf5;display:block;margin-bottom:4px}
.empty{color:#8b98b8;text-align:center;padding:34px;border:1px dashed #2a3a60;border-radius:12px}
footer{text-align:center;color:#5b6a8f;font-size:12.5px;padding:18px}
@media(max-width:1020px){main{grid-template-columns:1fr}.feats{grid-template-columns:1fr}}
</style></head><body>
<header><div class=hwrap>
<div class=brand>__LOGO__<div><b>tradagent</b><small>Real-time AI trading signals</small></div></div>
<div class=live><b><span id=activeN>0</span> Active Signals<i class=dot></i></b><small>Updated: <span id=upd>—</span></small></div>
</div></header>
<main>
<aside>
<div class=card>
<h2>Generate Trading Signals</h2>
<p class=lead>Get BUY/SELL/HOLD recommendations based on live market &amp; social data</p>
<div class=how><b>How Signals Are Generated:</b><ol>
<li><b>Assets:</b> analyzes BTC, ETH, SOL, BNB, XRP — one signal per coin</li>
<li><b>Market Data:</b> live prices, RSI, momentum from Binance + CoinGecko</li>
<li><b>AI Analysis:</b> Gemini or local quant engine → BUY/SELL/HOLD + confidence</li>
<li><b>Storage:</b> signals saved to SQLite and displayed instantly</li>
</ol></div>
<div class=checks><span><i>✓</i>Market Data</span><span><i>✓</i>Hybrid AI</span><span><i>✓</i>Real-time</span><span><i>✓</i>Confidence Scoring</span></div>
<button id=go onclick="run()">⚡ Generate Trading Signals</button>
<div class=bar><i id=pb></i></div>
<p id=st>Ready. Zero API keys required.</p>
</div>
<div class=card>
<h2>Metrics Explained</h2>
<dl class=gloss>
<dt>Mentions</dt><dd>Social posts mentioning the asset in the last 24h (LunarCrush).</dd>
<dt>Interactions</dt><dd>Total social engagement: likes, shares, replies.</dd>
<dt>Creators</dt><dd>Unique content creators — diversity vs. manipulation.</dd>
<dt>RSI-14</dt><dd>Momentum oscillator: &lt;30 oversold, &gt;70 overbought.</dd>
<dt>Momentum</dt><dd>Price change over the last 48h of hourly candles.</dd>
<dt>Galaxy Score</dt><dd>0–100 asset-health indicator (LunarCrush).</dd>
</dl>
</div>
</aside>
<section>
<div class="card hero">
<h1>Beat the Market with Social Intelligence</h1>
<p>Get trading signals before price movements happen by analyzing market &amp; social data</p>
<div class=feats>
<div><span class="tile t-blue">💬</span><h3>Market Data First</h3><p>Track live prices, RSI, momentum and engagement across markets. Real moves often start before the crowd notices.</p></div>
<div><span class="tile t-purple">⚡</span><h3>AI-Powered Decisions</h3><p>Gemini AI — or the built-in quant engine — turns complex patterns into clear BUY/SELL/HOLD calls with confidence scores.</p></div>
<div><span class="tile t-green">◈</span><h3>Zero-Setup Edge</h3><p>No API keys, no cloud accounts. Parallel fetching, smart caching and local SQLite give you answers in seconds.</p></div>
</div>
</div>
<div class=sec-h><h2>Latest Trading Signals</h2></div>
<p id=sigsub>Press “Generate Trading Signals” to run a fresh analysis.</p>
<div id=sigs><div class=empty>No signals yet.</div></div>
</section>
</main>
<footer>tradagent v1.0 — Binance + CoinGecko + hybrid AI engine<br>© 2026 salim-slimani. Educational use only — not financial advice.</footer>
<script>
const $=id=>document.getElementById(id);
const fmtN=v=>{if(v==null||v===''||isNaN(+v))return'—';v=+v;if(v>=1e9)return(v/1e9).toFixed(1)+'B';if(v>=1e6)return(v/1e6).toFixed(1)+'M';if(v>=1e3)return(v/1e3).toFixed(1)+'K';return Math.round(v).toLocaleString();};
const fmt$=v=>(v==null||isNaN(+v))?'—':'$'+(+v).toLocaleString(undefined,{maximumFractionDigits:+v<10?3:2});
const fmtT=t=>{try{return new Date(t*1000).toLocaleString();}catch(_){return'';}};
const arrow=s=>s==='BUY'?'▲':s==='SELL'?'▼':'—';
function card(x){
 const m=x.metrics||{},sg=x.signal;
 const chg=+m.change_24h||0, chCls=chg>0?'up':chg<0?'down':'';
 const alt=m.social_altrank?'#'+m.social_altrank:'—';
 const gal=(m.social_galaxy_score!=null&&m.social_galaxy_score!==50)?m.social_galaxy_score+'/100':'—';
 return `<div class=sigcard>
 <div class=s-top><span class=badge>${x.symbol}</span><div><b>$${x.symbol}</b><small>${fmtT(x.created_at)} · ${x.engine}</small></div><span class="pill ${sg}">${arrow(sg)} ${sg}</span></div>
 <div class=conf><span>AI Confidence</span><b>${x.confidence}%</b></div>
 <div class=cbar><i class="${sg}" style="width:${x.confidence}%"></i></div>
 <div class=tiles>
 <div class=tilebox>💬 Mentions<b>${fmtN(m.social_mentions)}</b></div>
 <div class=tilebox>⚡ Interactions<b>${fmtN(m.social_interactions)}</b></div>
 <div class=tilebox>👥 Creators<b>${fmtN(m.social_creators)}</b></div>
 </div>
 <div class=tiles2>
 <div class=tilebox>№ AltRank<b>${alt}</b></div>
 <div class=tilebox>★ Galaxy Score<b>${gal}</b></div>
 </div>
 <div class=mkt><span>Price <b>${fmt$(m.price)}</b></span><span class="${chCls}">24h ${chg>0?'+':''}${chg.toFixed?chg.toFixed(2):chg}%</span><span>RSI <b>${m.rsi_14??'—'}</b></span><span>Mom <b>${m.momentum_48h??'—'}%</b></span></div>
 <div class=analysis><b>AI Analysis</b>${x.reasoning||''}</div>
 </div>`;
}
function render(s){
 $('activeN').textContent=s.length;
 if(s.length){const t=Math.max(...s.map(x=>x.created_at||0));$('upd').textContent=fmtT(t);$('sigsub').textContent=`Showing ${s.length} most recent signals • Last updated: ${fmtT(t)}`;}
 $('sigs').innerHTML=s.length?s.map(card).join(''):'<div class=empty>No signals yet.</div>';
}
function fail(msg){$('st').textContent='❌ '+msg;$('go').disabled=false;}
async function run(){$('go').disabled=true;$('st').textContent='⏳ Analyzing market data...';
 let r;try{r=await fetch('/api/run',{method:'POST'});}catch(e){fail('cannot reach server');return;}
 if(!r.ok){let t='';try{t=((await r.json()).traceback||'').split('\\n').slice(-3).join(' ');}catch(_){}fail('server error '+r.status+(t?' — /api/debug: '+t:''));return;}
 let j=await r.json();
 if(j.error){fail(j.error+' — open /api/debug for details');return;}
 if(j.signals&&j.signals.length){render(j.signals);$('pb').style.width='100%';$('st').textContent='✅ '+(j.summary||'Done')+' ('+(j.duration_s||'?')+'s)';$('go').disabled=false;}
 else poll(j.job_id);
}
async function poll(id){let r=await fetch('/api/job?id='+id);
 if(!r.ok){fail('server error '+r.status);return;}
 let j=await r.json();if(j.error){fail(j.error);return;}
 $('pb').style.width=j.progress+'%';$('st').textContent=(j.step_message||'Working...')+' ('+j.progress+'%)';
 if(j.status!=='completed')setTimeout(()=>poll(id),600);else{load();$('go').disabled=false;}
}
async function load(){try{let r=await fetch('/api/signals');if(r.ok)render(await r.json());}catch(_){}}
load();
</script></body></html>"""

PAGE = PAGE.replace("__LOGO__", LOGO_SVG)


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
