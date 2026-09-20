"""Central config — fast, env-driven, zero required keys."""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _symbols() -> list[str]:
    raw = os.getenv("TRADAGENT_SYMBOLS", "BTC,ETH,SOL,BNB,XRP")
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


@dataclass
class Settings:
    symbols: list[str] = field(default_factory=_symbols)
    currency: str = os.getenv("TRADAGENT_CURRENCY", "usd").lower()
    # Vercel serverless filesystem is read-only except /tmp
    db_path: str = os.getenv("TRADAGENT_DB_PATH",
                             "/tmp/tradagent.db" if os.getenv("VERCEL") else "data/tradagent.db")
    cache_ttl: int = int(os.getenv("TRADAGENT_CACHE_TTL", "300"))
    gemini_key: str = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    lunarcrush_key: str = os.getenv("LUNARCRUSH_API_KEY", "")
    discord_webhook: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    @property
    def use_gemini(self) -> bool:
        return bool(self.gemini_key)

    @property
    def use_lunarcrush(self) -> bool:
        return bool(self.lunarcrush_key)


settings = Settings()
