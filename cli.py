"""tradagent CLI — practical entry points."""
import argparse
import json
import sys

from agent import Agent
from backtest import backtest
from config import settings
from database import Store


def cmd_run(args):
    syms = [s.upper() for s in (args.symbols.split(",") if args.symbols else settings.symbols)]

    def bar(jid, p, step, msg):
        n = int(p / 5)
        sys.stdout.write(f"\r[{'█'*n}{'░'*(20-n)}] {p}% | {msg}   ")
        sys.stdout.flush()

    agent = Agent(progress_cb=bar)
    res = agent.run(syms)
    print()
    print(f"\n✅ {res['summary']}  ({res['duration_s']}s)")
    for s in res["signals"]:
        flag = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}[s["signal"]]
        print(f"{flag} {s['symbol']:6} {s['signal']:4} {s['confidence']:3}%  ${s['metrics'].get('price',0):,.2f}  — {s['reasoning']}")
    if args.json:
        print(json.dumps(res, ensure_ascii=False, default=float))


def cmd_signals(args):
    for s in Store(settings.db_path).latest_signals(args.limit):
        print(f"{s['symbol']:6} {s['signal']:4} {s['confidence']:3}% [{s['engine']}] — {s['reasoning']}")


def cmd_backtest(args):
    for sym in args.symbols.split(","):
        print(json.dumps(backtest(sym.strip()), ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(prog="tradagent", description="🤖 tradagent — fast AI trading agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run analysis and generate signals")
    r.add_argument("--symbols", default=None, help="BTC,ETH,SOL")
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("signals", help="show latest signals")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_signals)
    b = sub.add_parser("backtest", help="quick strategy backtest")
    b.add_argument("--symbols", default="BTC,ETH,SOL")
    b.set_defaults(fn=cmd_backtest)
    d = sub.add_parser("dashboard", help="start the live dashboard")
    d.add_argument("--port", type=int, default=8000)
    d.set_defaults(fn=lambda a: __import__("dashboard").serve(a.port))
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
