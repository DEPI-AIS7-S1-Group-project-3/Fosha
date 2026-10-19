"""Backend settings, read once from the environment (.env is loaded if present)."""
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # .env loading is optional; real env vars still work
    pass


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _list(name: str, default: str) -> List[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "RehlaGuide API"
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = field(default_factory=lambda: _list("CORS_ORIGINS", "*"))
    cache_ttl_seconds: int = field(default_factory=lambda: _int("CACHE_TTL_SECONDS", 3600))
    cache_max_entries: int = field(default_factory=lambda: _int("CACHE_MAX_ENTRIES", 512))
    session_ttl_seconds: int = field(default_factory=lambda: _int("SESSION_TTL_SECONDS", 3600))
    stale_after_days: int = field(default_factory=lambda: _int("STALE_AFTER_DAYS", 180))
    max_message_chars: int = field(default_factory=lambda: _int("MAX_MESSAGE_CHARS", 2000))
    # Load the embedding model + Chroma at startup so the first request is not slow.
    warmup_on_startup: bool = field(default_factory=lambda: _bool("WARMUP_ON_STARTUP", True))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
