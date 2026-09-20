"""Simple backtest: HOLD-signal strategy sanity check on Binance klines."""
import data_providers as dp


def backtest(symbol: str, hours: int = 168) -> dict:
    klines = dp.binance_klines(symbol.upper(), "1h", min(hours, 500))
    closes = [float(k[4]) for k in klines]
    if len(closes) < 30:
        return {"symbol": symbol, "error": "no data"}
    # naive: buy when 48h momentum < -5% (oversold bounce), sell when > +8%
    cash, coin, trades = 1000.0, 0.0, 0
    for i in range(24, len(closes)):
        mom = (closes[i] - closes[i - 24]) / closes[i - 24] * 100
        if coin == 0 and mom < -5:
            coin, cash, trades = cash / closes[i], 0.0, trades + 1
        elif coin > 0 and mom > 8:
            cash, coin, trades = coin * closes[i], 0.0, trades + 1
    equity = cash + coin * closes[-1]
    buy_hold = closes[-1] / closes[24] * 1000
    return {"symbol": symbol.upper(), "strategy_equity": round(equity, 2),
            "buy_hold_equity": round(buy_hold, 2), "trades": trades,
            "edge_vs_hold_pct": round((equity / buy_hold - 1) * 100, 2)}
