"""Live integration test against the real DexScreener API.

Skipped by default; run with ``uv run pytest -m live``. Catches drift between the live
API contract and our raw models.
"""

from __future__ import annotations

import pytest

from langley_risk.providers.dexscreener import DexScreenerProvider

WSOL = "So11111111111111111111111111111111111111112"

pytestmark = pytest.mark.live


async def test_fetches_wsol_snapshot_from_live_api() -> None:
    provider = DexScreenerProvider("https://api.dexscreener.com", 10.0)
    try:
        snapshot = await provider.get_market_snapshot(WSOL)
    finally:
        await provider.aclose()
    assert snapshot.token_address
    assert snapshot.liquidity_usd is not None and snapshot.liquidity_usd > 0
    assert snapshot.source_provider == "dexscreener"
