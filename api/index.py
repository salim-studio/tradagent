"""Vercel serverless entrypoint for tradagent.

Vercel maps this file to the /api route. Combined with vercel.json rewrites:
  GET  /            -> dashboard HTML
  GET  /api/signals -> latest signals (JSON)
  GET  /api/job     -> job status (JSON)
  POST /api/run     -> run analysis synchronously, returns {job_id, summary, signals}

Docs: https://vercel.com/docs/functions/runtimes/python#python-entrypoints
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import Agent  # noqa: E402
from config import settings  # noqa: E402
from dashboard import PAGE  # noqa: E402
from database import Store  # noqa: E402


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

    def _route(self):
        """Support both /api/<action> paths and ?action=<action> queries."""
        u = urlparse(self.path)
        q = parse_qs(u.query)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "api":
            return parts[1], q
        return q.get("action", [""])[0], q

    def do_GET(self):
        action, q = self._route()
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

    def do_POST(self):
        action, _ = self._route()
        if action == "run":
            store = Store(settings.db_path)
            try:
                res = Agent(store=store).run()
                return self._json(res)
            finally:
                store.db.close()
        return self._json({"error": "not found"}, 404)

    def log_message(self, *a):
        pass
