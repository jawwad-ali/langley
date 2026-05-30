"""Application settings, loaded from environment variables / .env.

All settings use the ``LANGLEY_RISK_`` prefix (except ``OPENAI_API_KEY``, which the
OpenAI SDK reads directly). ``get_settings()`` is cached so the environment is read
once per process; tests can clear the cache or pass an explicit ``Settings`` instance.
"""

from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from langley_risk.providers.base import ProviderName


def load_env_file() -> None:
    """Load a root ``.env`` into ``os.environ``.

    pydantic-settings reads ``.env`` for our ``LANGLEY_RISK_*`` fields, but it does NOT
    export keys into the process environment, and ``uv run`` doesn't auto-load ``.env``.
    The OpenAI SDK reads ``OPENAI_API_KEY`` from ``os.environ`` directly, so process
    entrypoints call this first to make a root ``.env`` work for both.
    """
    load_dotenv()


class Settings(BaseSettings):
    """Runtime configuration for langley_risk."""

    model_config = SettingsConfigDict(
        env_prefix="LANGLEY_RISK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM / agent ---
    model: str = "gpt-4o"
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_turns: int = Field(default=6, ge=1, le=20)

    # --- Data provider ---
    # Default stays DexScreener (market-only). Set to "helius"/"composite" to also
    # enrich with Helius contract data (requires helius_api_key).
    provider: ProviderName = ProviderName.DEXSCREENER
    dexscreener_base_url: str = "https://api.dexscreener.com"
    http_timeout_seconds: float = Field(default=10.0, gt=0.0)

    # --- Helius contract enrichment (optional) ---
    helius_api_key: str | None = None
    helius_rpc_url: str = "https://mainnet.helius-rpc.com"

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = False

    # --- Evals / live gating ---
    live: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
