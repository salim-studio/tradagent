"""SQLite storage — replaces Supabase for speed/offline. WAL mode, indexed."""
import json
import os
import sqlite3
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS trading_signals(
 id TEXT PRIMARY KEY, symbol TEXT NOT NULL, signal TEXT NOT NULL,
 confidence INTEGER NOT NULL, reasoning TEXT NOT NULL, engine TEXT DEFAULT 'local',
 metrics TEXT NOT NULL, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sig_sym ON trading_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_sig_time ON trading_signals(created_at DESC);
CREATE TABLE IF NOT EXISTS analysis_jobs(
 id TEXT PRIMARY KEY, status TEXT DEFAULT 'started', current_step TEXT DEFAULT '',
 step_message TEXT DEFAULT '', progress INTEGER DEFAULT 0,
 signals_generated INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0,
 started_at REAL NOT NULL, updated_at REAL NOT NULL);
"""


def connect(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    return c


class Store:
    def __init__(self, path: str):
        self.db = connect(path)

    def new_job(self) -> str:
        jid = uuid.uuid4().hex[:12]
        now = time.time()
        self.db.execute("INSERT INTO analysis_jobs VALUES(?,?,?,?,?,?,?, ?,?)",
                        (jid, "started", "init", "starting", 0, 0, 0, now, now))
        self.db.commit()
        return jid

    def job_update(self, jid, status=None, step=None, msg=None, progress=None, signals=None):
        cur = self.db.execute("SELECT status,current_step,step_message,progress,signals_generated FROM analysis_jobs WHERE id=?", (jid,))
        row = cur.fetchone()
        if not row: return
        st, cs, sm, pg, sg = row
        self.db.execute("UPDATE analysis_jobs SET status=?,current_step=?,step_message=?,progress=?,signals_generated=?,updated_at=? WHERE id=?",
                        (status or st, step or cs, msg or sm,
                         progress if progress is not None else pg,
                         signals if signals is not None else sg, time.time(), jid))
        self.db.commit()

    def job_finish(self, jid, signals_n, started):
        self.db.execute("UPDATE analysis_jobs SET status='completed',progress=100,signals_generated=?,duration_ms=?,updated_at=? WHERE id=?",
                        (signals_n, int((time.time() - started) * 1000), time.time(), jid))
        self.db.commit()

    def save_signals(self, signals: list[dict]):
        now = time.time()
        for s in signals:
            self.db.execute("INSERT OR REPLACE INTO trading_signals VALUES(?,?,?,?,?,?,?,?)",
                            (uuid.uuid4().hex[:12], s["symbol"], s["signal"], s["confidence"],
                             s["reasoning"], s.get("engine", "local"),
                             json.dumps(s.get("metrics", {}), default=float), now))
        self.db.commit()

    def latest_signals(self, limit=50) -> list[dict]:
        cur = self.db.execute("SELECT symbol,signal,confidence,reasoning,engine,metrics,created_at FROM trading_signals ORDER BY created_at DESC LIMIT ?", (limit,))
        out = []
        for sym, sig, conf, rea, eng, met, ts in cur.fetchall():
            try:
                met = json.loads(met) if met else {}
            except Exception:
                met = {}
            out.append({"symbol": sym, "signal": sig, "confidence": conf,
                        "reasoning": rea, "engine": eng, "metrics": met, "created_at": ts})
        return out

    def job(self, jid) -> dict | None:
        cur = self.db.execute("SELECT * FROM analysis_jobs WHERE id=?", (jid,))
        r = cur.fetchone()
        if not r: return None
        k = ("id", "status", "current_step", "step_message", "progress", "signals_generated", "duration_ms", "started_at", "updated_at")
        return dict(zip(k, r))
