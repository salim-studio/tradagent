"""tradagent pipeline — 7-step local analysis: fast + parallel.

Steps: init → symbols → fetch → analyze → save → summary → done
Typical runtime: 2-8s for 5 symbols.
"""
import time
from concurrent.futures import ThreadPoolExecutor

import ai_engine
import data_providers as dp
from config import settings
from database import Store

STEPS = [
    (14, "init", "Initializing analysis..."),
    (28, "symbols", "Preparing symbol list..."),
    (42, "fetch", "Fetching market data..."),
    (57, "analyze", "Generating signals with AI..."),
    (71, "save", "Saving to database..."),
    (85, "summary", "Building summary..."),
    (100, "done", "Analysis complete ✅"),
]


class Agent:
    def __init__(self, store: Store | None = None, progress_cb=None):
        self.store = store or Store(settings.db_path)
        self.cb = progress_cb or (lambda jid, p, s, m: None)

    def _emit(self, jid, p, s, m):
        self.store.job_update(jid, step=s, msg=m, progress=p)
        try: self.cb(jid, p, s, m)
        except Exception: pass

    def run(self, symbols: list[str] | None = None) -> dict:
        symbols = [s.upper() for s in (symbols or settings.symbols)]
        t0 = time.time()
        jid = self.store.new_job()
        self._emit(jid, 14, "init", f"Initializing analysis for {len(symbols)} symbols...")
        self._emit(jid, 28, "symbols", f"Symbols: {', '.join(symbols)}")

        # 3) parallel market fetch
        self._emit(jid, 42, "fetch", "Fetching market data (Binance + CoinGecko)...")
        metrics = dp.fetch_all(symbols)
        # enrich with coingecko fallback prices where binance failed
        cg = dp.coingecko_markets(symbols)
        for m in metrics:
            c = cg.get(m["symbol"])
            if c and not m.get("price"):
                m["price"] = c["price"]; m["change_24h"] = c["change_24h"]

        # 4) parallel AI analysis
        self._emit(jid, 57, "analyze",
                   f"AI analysis ({'Gemini' if settings.use_gemini else 'fast local engine'})...")
        with ThreadPoolExecutor(max_workers=8) as ex:
            signals = list(ex.map(ai_engine.analyze, metrics))

        # 5) save
        self._emit(jid, 71, "save", "Saving signals...")
        self.store.save_signals(signals)
        self.store.job_update(jid, signals=len(signals))

        # 6) summary
        self._emit(jid, 85, "summary", "Building summary...")
        buys = sum(1 for s in signals if s["signal"] == "BUY")
        sells = sum(1 for s in signals if s["signal"] == "SELL")
        summary = f"BUY: {buys} | SELL: {sells} | HOLD: {len(signals)-buys-sells}"

        # 7) done + optional discord
        self._emit(jid, 100, "done", f"Done ✅ — {summary}")
        self.store.job_finish(jid, len(signals), t0)
        self._notify(summary, signals)
        return {"job_id": jid, "signals": signals, "summary": summary,
                "duration_s": round(time.time() - t0, 2)}

    def _notify(self, summary, signals):
        if not settings.discord_webhook: return
        try:
            import requests
            lines = [f"**tradagent** — {summary}"] + \
                    [f"{s['symbol']}: {s['signal']} ({s['confidence']}%)" for s in signals]
            requests.post(settings.discord_webhook, json={"content": "\n".join(lines)}, timeout=6)
        except Exception:
            pass
