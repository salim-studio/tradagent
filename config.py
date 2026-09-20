"""Central config — fast, env-driven, zero required keys.

Resilient to empty/malformed env values (e.g. vars created with empty values
in the Vercel dashboard): any blank or invalid value falls back to defaults
instead of crashing at import time.
"""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _env(key: str, default: str) -> str:
    v = os.getenv(key)
    return v if v not in (None, "") else default


def _int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _symbols() -> list[str]:
    syms = [s.strip().upper() for s in _env("TRADAGENT_SYMBOLS", "BTC,ETH,SOL,BNB,XRP").split(",") if s.strip()]
    return syms or ["BTC", "ETH", "SOL", "BNB", "XRP"]


_DEFAULT_DB = "/tmp/tradagent.db" if os.getenv("VERCEL") else "data/tradagent.db"


@dataclass
class Settings:
    symbols: list[str] = field(default_factory=_symbols)
    currency: str = field(default_factory=lambda: _env("TRADAGENT_CURRENCY", "usd").lower())
    # Vercel serverless filesystem is read-only except /tmp
    db_path: str = field(default_factory=lambda: _env("TRADAGENT_DB_PATH", _DEFAULT_DB))
    cache_ttl: int = field(default_factory=lambda: _int("TRADAGENT_CACHE_TTL", 300))
    gemini_key: str = field(default_factory=lambda: _env("GOOGLE_GEMINI_API_KEY", ""))
    lunarcrush_key: str = field(default_factory=lambda: _env("LUNARCRUSH_API_KEY", ""))
    discord_webhook: str = field(default_factory=lambda: _env("DISCORD_WEBHOOK_URL", ""))

    @property
    def use_gemini(self) -> bool:
        return bool(self.gemini_key)

    @property
    def use_lunarcrush(self) -> bool:
        return bool(self.lunarcrush_key)


settings = Settings()
