"""Construct a ``DataProvider`` from settings — the single place provider choice lives.

- ``dexscreener`` (default): market data only.
- ``helius`` / ``composite``: DexScreener market data enriched with Helius contract
  data (requires ``helius_api_key``). Helius alone has no market/liquidity view, so
  both names resolve to the same composite.
"""

from __future__ import annotations

from langley_risk.config import Settings
from langley_risk.errors import ConfigError
from langley_risk.providers.base import DataProvider, ProviderName
from langley_risk.providers.composite import CompositeProvider
from langley_risk.providers.dexscreener import DexScreenerProvider
from langley_risk.providers.helius import HeliusEnricher

_ENRICHED = {ProviderName.HELIUS, ProviderName.COMPOSITE}


def _dexscreener(settings: Settings) -> DexScreenerProvider:
    return DexScreenerProvider(
        base_url=settings.dexscreener_base_url,
        timeout_seconds=settings.http_timeout_seconds,
    )


def get_provider(settings: Settings) -> DataProvider:
    """Return a live data provider matching ``settings.provider``."""
    if settings.provider == ProviderName.DEXSCREENER:
        return _dexscreener(settings)

    if settings.provider in _ENRICHED:
        if not settings.helius_api_key:
            raise ConfigError(
                f"provider={settings.provider.value!r} requires LANGLEY_RISK_HELIUS_API_KEY"
            )
        enricher = HeliusEnricher(
            api_key=settings.helius_api_key,
            rpc_url=settings.helius_rpc_url,
            timeout_seconds=settings.http_timeout_seconds,
        )
        return CompositeProvider(primary=_dexscreener(settings), enricher=enricher)

    raise ConfigError(f"Unsupported provider: {settings.provider!r}")
