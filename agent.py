"""tradagent pipeline — 7 steps mirroring the reference, but local + parallel + fast.

Steps: init → symbols → fetch → analyze → save → summary → done
Typical runtime: 3-8s for 5 symbols (vs 30-45s in reference).
"""
import time
from concurrent.futures import ThreadPoolExecutor

import ai_engine
import data_providers as dp
from config import settings
from database import Store

STEPS = [
    (14, "init", "تهيئة التحليل..."),
    (28, "symbols", "تجهيز قائمة العملات..."),
    (42, "fetch", "جلب بيانات السوق..."),
    (57, "analyze", "توليد الإشارات بالذكاء الاصطناعي..."),
    (71, "save", "حفظ في قاعدة البيانات..."),
    (85, "summary", "توليد الملخص..."),
    (100, "done", "اكتمل التحليل ✅"),
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
        self._emit(jid, 14, "init", f"تهيئة التحليل لـ {len(symbols)} عملة...")
        self._emit(jid, 28, "symbols", f"العملات: {', '.join(symbols)}")

        # 3) parallel market fetch
        self._emit(jid, 42, "fetch", "جلب بيانات السوق (Binance + CoinGecko)...")
        metrics = dp.fetch_all(symbols)
        # enrich with coingecko fallback prices where binance failed
        cg = dp.coingecko_markets(symbols)
        for m in metrics:
            c = cg.get(m["symbol"])
            if c and not m.get("price"):
                m["price"] = c["price"]; m["change_24h"] = c["change_24h"]

        # 4) parallel AI analysis
        self._emit(jid, 57, "analyze",
                   f"تحليل AI ({'Gemini' if settings.use_gemini else 'محرك محلي سريع'})...")
        with ThreadPoolExecutor(max_workers=8) as ex:
            signals = list(ex.map(ai_engine.analyze, metrics))

        # 5) save
        self._emit(jid, 71, "save", "حفظ الإشارات...")
        self.store.save_signals(signals)
        self.store.job_update(jid, signals=len(signals))

        # 6) summary
        self._emit(jid, 85, "summary", "توليد الملخص...")
        buys = sum(1 for s in signals if s["signal"] == "BUY")
        sells = sum(1 for s in signals if s["signal"] == "SELL")
        summary = f"شراء: {buys} | بيع: {sells} | انتظار: {len(signals)-buys-sells}"

        # 7) done + optional discord
        self._emit(jid, 100, "done", f"اكتمل ✅ — {summary}")
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
