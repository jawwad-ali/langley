"""Construct a ``DataProvider`` from settings — the single place provider choice lives.

Adding Helius/Birdeye later means adding a branch here; no caller changes.
"""

from __future__ import annotations

from langley_risk.config import Settings
from langley_risk.errors import ConfigError
from langley_risk.providers.base import DataProvider, ProviderName
from langley_risk.providers.dexscreener import DexScreenerProvider


def get_provider(settings: Settings) -> DataProvider:
    """Return a live data provider matching ``settings.provider``."""
    if settings.provider == ProviderName.DEXSCREENER:
        return DexScreenerProvider(
            base_url=settings.dexscreener_base_url,
            timeout_seconds=settings.http_timeout_seconds,
        )
    raise ConfigError(f"Unsupported provider: {settings.provider!r}")
