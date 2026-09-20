"""Hybrid AI engine: Gemini when key exists, else fast local quant engine.

Local engine = weighted score of RSI + momentum + 24h change + social.
Calibrated to emit BUY/SELL/HOLD with 0-100 confidence — no API, <1ms.
"""
from config import settings

PROMPT = """You are a crypto trading analyst. Given JSON market metrics, reply ONLY valid JSON:
{{"signal":"BUY|SELL|HOLD","confidence":0-100,"reasoning":"one Arabic sentence"}}"""


def local_score(m: dict) -> tuple[str, int, str]:
    rsi = m.get("rsi_14", 50)
    mom = m.get("momentum_48h", 0)
    chg = m.get("change_24h", 0) or 0
    gal = m.get("social_galaxy_score", 50)
    sent = m.get("social_sentiment", 50)
    vol = m.get("volatility", 0)

    score = 0.0
    # RSI mean-reversion (30%) — oversold bullish
    if rsi < 30: score += 30
    elif rsi < 40: score += 15
    elif rsi > 70: score -= 30
    elif rsi > 60: score -= 15
    # momentum (30%)
    score += max(min(mom * 3, 30), -30)
    # 24h change anti-chase (15%): avoid buying parabolic pumps
    if chg > 10: score -= 10
    elif chg < -10: score += 10
    # social health (25%)
    score += (gal - 50) * 0.3 + (sent - 50) * 0.2

    reasons = []
    reasons.append(f"RSI {rsi}")
    reasons.append(f"زخم {mom}%")
    reasons.append(f"تغير 24س {round(chg,1)}%")
    if gal != 50: reasons.append(f"Galaxy {gal}")
    if vol > 8: reasons.append("تذبذب عالٍ — حذر")

    if score >= 18: return "BUY", min(55 + int(score), 95), "إشارة شراء: " + "، ".join(reasons)
    if score <= -18: return "SELL", min(55 + int(-score), 95), "إشارة بيع: " + "، ".join(reasons)
    conf = max(40, 55 - int(abs(score)))
    return "HOLD", conf, "انتظار: " + "، ".join(reasons)


def gemini_signal(m: dict) -> tuple[str, int, str] | None:
    if not settings.use_gemini:
        return None
    try:
        import google.generativeai as genai  # optional dep
        import json
        genai.configure(api_key=settings.gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(f"{PROMPT}\n{json.dumps(m, default=float)}",
                                      generation_config={"response_mime_type": "application/json"})
        d = json.loads(resp.text)
        sig = str(d.get("signal", "HOLD")).upper()
        if sig not in ("BUY", "SELL", "HOLD"): sig = "HOLD"
        return sig, int(max(0, min(100, d.get("confidence", 60)))), str(d.get("reasoning", ""))[:300]
    except Exception:
        return None  # fail-open to local engine


def analyze(m: dict) -> dict:
    """Single entry: try Gemini, always fall back to local. Never raises."""
    try:
        g = gemini_signal(m)
        if g:
            sig, conf, why = g
            return {"symbol": m["symbol"], "signal": sig, "confidence": conf,
                    "reasoning": why, "engine": "gemini", "metrics": m}
    except Exception:
        pass
    sig, conf, why = local_score(m)
    return {"symbol": m["symbol"], "signal": sig, "confidence": conf,
            "reasoning": why, "engine": "local", "metrics": m}
