"""Fast market data providers — free public APIs, parallel, cached.

Priority (fastest first):
1. Binance public klines/ticker (no key, ~100ms)
2. CoinGecko free markets (no key, fallback)
3. LunarCrush (only if API key present)
"""
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import settings

BINANCE = "https://api.binance.com"
COINGECKO = "https://api.coingecko.com/api/v3"
LUNARCRUSH = "https://lunarcrush.com/api4/public/coins"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "tradagent/1.0"})

_cache: dict[str, tuple[float, dict]] = {}

SYMBOL_MAP = {  # tradagent symbol -> binance pair + coingecko id
    "BTC": ("BTCUSDT", "bitcoin"),
    "ETH": ("ETHUSDT", "ethereum"),
    "SOL": ("SOLUSDT", "solana"),
    "BNB": ("BNBUSDT", "binancecoin"),
    "XRP": ("XRPUSDT", "ripple"),
    "DOGE": ("DOGEUSDT", "dogecoin"),
    "ADA": ("ADAUSDT", "cardano"),
    "AVAX": ("AVAXUSDT", "avalanche-2"),
    "LINK": ("LINKUSDT", "chainlink"),
    "TON": ("TONUSDT", "the-open-network"),
}


def _cached(key: str):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < settings.cache_ttl:
        return hit[1]
    return None


def _put(key: str, val: dict):
    _cache[key] = (time.time(), val)


def binance_klines(symbol: str, interval: str = "1h", limit: int = 48) -> list[list]:
    pair = SYMBOL_MAP.get(symbol.upper(), (f"{symbol.upper()}USDT", ""))[0]
    try:
        r = SESSION.get(f"{BINANCE}/api/v3/klines",
                        params={"symbol": pair, "interval": interval, "limit": limit},
                        timeout=8)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return []


def binance_ticker(symbol: str) -> dict:
    pair = SYMBOL_MAP.get(symbol.upper(), (f"{symbol.upper()}USDT", ""))[0]
    try:
        r = SESSION.get(f"{BINANCE}/api/v3/ticker/24hr", params={"symbol": pair}, timeout=8)
        if r.ok:
            d = r.json()
            return {
                "price": float(d.get("lastPrice", 0)),
                "change_24h": float(d.get("priceChangePercent", 0)),
                "high": float(d.get("highPrice", 0)),
                "low": float(d.get("lowPrice", 0)),
                "volume": float(d.get("quoteVolume", 0)),
            }
    except Exception:
        pass
    return {}


def coingecko_markets(symbols: list[str]) -> dict[str, dict]:
    ids = ",".join(SYMBOL_MAP[s][1] for s in symbols if s in SYMBOL_MAP)
    if not ids:
        return {}
    try:
        r = SESSION.get(f"{COINGECKO}/coins/markets",
                        params={"vs_currency": settings.currency, "ids": ids,
                                "price_change_percentage": "24h,7d"}, timeout=10)
        if r.ok:
            out = {}
            for c in r.json():
                for sym, (_, cid) in SYMBOL_MAP.items():
                    if cid == c["id"]:
                        out[sym] = {
                            "price": c.get("current_price", 0),
                            "change_24h": c.get("price_change_percentage_24h", 0) or 0,
                            "change_7d": c.get("price_change_percentage_7d_in_currency", 0) or 0,
                            "market_cap": c.get("market_cap", 0),
                            "volume": c.get("total_volume", 0),
                        }
            return out
    except Exception:
        pass
    return {}


def lunarcrush_social(symbol: str) -> dict:
    """Only called when key exists; never blocks the pipeline."""
    if not settings.use_lunarcrush:
        return {}
    try:
        r = SESSION.get(f"{LUNARCRUSH}/{symbol.lower()}/v1",
                        headers={"Authorization": f"Bearer {settings.lunarcrush_key}"},
                        timeout=8)
        if r.ok:
            d = r.json().get("data", {})
            return {
                "mentions": d.get("mentions", 0),
                "interactions": d.get("interactions_24h", 0) or d.get("interactions", 0),
                "creators": d.get("num_creators", 0) or d.get("creators", 0),
                "galaxy_score": d.get("galaxy_score", 50) or 50,
                "altrank": d.get("alt_rank", 0),
                "sentiment": d.get("sentiment", 50),
            }
    except Exception:
        pass
    return {}


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
    gains, losses = gains[-period:], losses[-period:]
    ag, al = sum(gains) / period, sum(losses) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return round(100 - 100 / (1 + rs), 2)


def _momentum(closes: list[float]) -> float:
    if len(closes) < 2:
        return 0.0
    return round((closes[-1] - closes[0]) / closes[0] * 100, 2)


def fetch_one(symbol: str) -> dict:
    """Fetch + compute all metrics for one symbol (parallel-safe)."""
    ck = f"m:{symbol}"
    hit = _cached(ck)
    if hit:
        return hit
    symbol = symbol.upper()
    ticker = binance_ticker(symbol)
    klines = binance_klines(symbol)
    closes = [float(k[4]) for k in klines] if klines else []
    social = lunarcrush_social(symbol)

    price = ticker.get("price", closes[-1] if closes else 0)
    result = {
        "symbol": symbol,
        "price": price,
        "change_24h": ticker.get("change_24h", 0),
        "high_24h": ticker.get("high", 0),
        "low_24h": ticker.get("low", 0),
        "volume_24h": ticker.get("volume", 0),
        "rsi_14": _rsi(closes),
        "momentum_48h": _momentum(closes),
        "volatility": round((max(closes) - min(closes)) / closes[-1] * 100, 2) if closes else 0,
        **({"social_" + k: v for k, v in social.items()} if social else {}),
        "social_galaxy_score": social.get("galaxy_score", 50),
        "social_sentiment": social.get("sentiment", 50),
    }
    _put(ck, result)
    return result


def fetch_all(symbols: list[str], workers: int = 8) -> list[dict]:
    """Parallel fetch — key speed win vs sequential original."""
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(workers, max(len(symbols), 1))) as ex:
        futs = {ex.submit(fetch_one, s): s for s in symbols}
        for f in as_completed(futs):
            try:
                out.append(f.result())
            except Exception:
                out.append({"symbol": futs[f], "price": 0, "error": True})
    # keep requested order
    order = {s: i for i, s in enumerate(symbols)}
    return sorted(out, key=lambda d: order.get(d["symbol"], 99))
