"""Unit tests for DexScreener parsing, pair selection, and error mapping (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import (
    ProviderRateLimitedError,
    TokenNotFoundError,
)
from langley_risk.providers.dexscreener import DexScreenerProvider

BASE_URL = "https://api.dexscreener.com"
WSOL = "So11111111111111111111111111111111111111112"
TOKENS_PATH = f"/latest/dex/tokens/{WSOL}"


async def _fetch(query: str) -> MarketSnapshot:
    provider = DexScreenerProvider(BASE_URL, 10.0)
    try:
        return await provider.get_market_snapshot(query)
    finally:
        await provider.aclose()


class TestParsing:
    async def test_selects_deepest_liquidity_pair_and_maps_fields(
        self, raw_wsol_payload: str
    ) -> None:
        async with respx.mock(base_url=BASE_URL) as mock:
            mock.get(TOKENS_PATH).mock(return_value=httpx.Response(200, text=raw_wsol_payload))
            snapshot = await _fetch(WSOL)
        # Two pairs in the fixture; the $8.4M one must win over the $5k one.
        assert snapshot.liquidity_usd == 8_400_000.0
        assert snapshot.token_symbol == "WSOL"
        assert snapshot.price_usd == 168.42
        assert snapshot.buys_24h == 5210
        assert snapshot.sells_24h == 4870
        assert snapshot.age_hours is not None and snapshot.age_hours > 0
        assert snapshot.source_provider == "dexscreener"


class TestErrorMapping:
    async def test_empty_pairs_raises_not_found(self) -> None:
        async with respx.mock(base_url=BASE_URL) as mock:
            mock.get(TOKENS_PATH).mock(return_value=httpx.Response(200, json={"pairs": []}))
            with pytest.raises(TokenNotFoundError):
                await _fetch(WSOL)

    async def test_http_404_raises_not_found(self) -> None:
        async with respx.mock(base_url=BASE_URL) as mock:
            mock.get(TOKENS_PATH).mock(return_value=httpx.Response(404))
            with pytest.raises(TokenNotFoundError):
                await _fetch(WSOL)

    async def test_http_429_raises_rate_limited(self) -> None:
        async with respx.mock(base_url=BASE_URL) as mock:
            mock.get(TOKENS_PATH).mock(return_value=httpx.Response(429))
            with pytest.raises(ProviderRateLimitedError):
                await _fetch(WSOL)
