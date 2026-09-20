"""Vercel serverless entrypoint for tradagent.

Vercel maps this file to the /api route. Combined with vercel.json rewrites:
  GET  /            -> dashboard HTML
  GET  /api/signals -> latest signals (JSON)
  GET  /api/job     -> job status (JSON)
  GET  /api/debug   -> self-diagnostics (JSON) — open this if anything fails
  POST /api/run     -> run analysis synchronously, returns {job_id, summary, signals}

Design notes for serverless reliability:
- Project modules are imported LAZILY inside the request (never at module top),
  so an import problem becomes a readable JSON error, not an opaque crash.
- Every dispatch path is wrapped in try/except returning the traceback.
- Only stdlib is imported at module top (always available).

Docs: https://vercel.com/docs/functions/runtimes/python#python-entrypoints
"""
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _mods():
    """Lazy project imports — called per request inside try/except."""
    from agent import Agent
    from config import settings
    from dashboard import PAGE
    from database import Store
    return Agent, settings, PAGE, Store


def debug_info() -> dict:
    """Self-diagnostics: environment, bundled files, imports, sqlite, network."""
    info: dict = {
        "python": sys.version,
        "cwd": os.getcwd(),
        "vercel_env": os.getenv("VERCEL"),
        "root": ROOT,
        "path_has_root": ROOT in sys.path,
        "imports": {},
        "sqlite_tmp": None,
        "coingecko": None,
    }
    try:
        info["root_files"] = sorted(os.listdir(ROOT))
    except Exception as e:
        info["root_files"] = f"LIST FAIL: {e}"
    for name in ("agent", "config", "dashboard", "database",
                 "data_providers", "ai_engine", "requests", "dotenv"):
        try:
            __import__(name)
            info["imports"][name] = "ok"
        except Exception as e:
            info["imports"][name] = f"FAIL: {type(e).__name__}: {e}"
    try:
        import sqlite3
        c = sqlite3.connect("/tmp/tradagent_dbg.db")
        c.execute("CREATE TABLE IF NOT EXISTS t(a)")
        c.execute("INSERT INTO t VALUES (1)")
        c.commit()
        c.close()
        os.remove("/tmp/tradagent_dbg.db")
        info["sqlite_tmp"] = "ok"
    except Exception as e:
        info["sqlite_tmp"] = f"FAIL: {type(e).__name__}: {e}"
    try:
        import urllib.request
        r = urllib.request.urlopen("https://api.coingecko.com/api/v3/ping", timeout=8)
        info["coingecko"] = f"HTTP {r.status}"
    except Exception as e:
        info["coingecko"] = f"FAIL: {type(e).__name__}: {e}"
    return info


class handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(json.dumps(obj, ensure_ascii=False, default=float).encode(),
                   "application/json; charset=utf-8", code)

    def _error(self, where: str):
        self._json({"error": where, "traceback": traceback.format_exc()}, 500)

    def _route(self):
        """Support both /api/<action> paths and ?action=<action> queries."""
        u = urlparse(self.path)
        q = parse_qs(u.query)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "api":
            return parts[1], q
        return q.get("action", [""])[0], q

    def do_GET(self):
        try:
            action, q = self._route()
            if action == "debug":
                return self._json(debug_info())
            Agent, settings, PAGE, Store = _mods()
            store = Store(settings.db_path)
            try:
                if action == "signals":
                    return self._json(store.latest_signals())
                if action == "job":
                    j = store.job(q.get("id", [""])[0])
                    return self._json(j or {"error": "not found"})
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            finally:
                store.db.close()
        except Exception:
            self._error("GET failed")

    def do_POST(self):
        try:
            action, _ = self._route()
            if action == "run":
                Agent, settings, PAGE, Store = _mods()
                store = Store(settings.db_path)
                try:
                    return self._json(Agent(store=store).run())
                finally:
                    store.db.close()
            return self._json({"error": "not found"}, 404)
        except Exception:
            self._error("POST failed")

    def log_message(self, *a):
        pass
