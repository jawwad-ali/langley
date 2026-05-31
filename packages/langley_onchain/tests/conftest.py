"""Shared test fixtures for On-Chain Forensics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from langley_risk.config import Settings
from langley_risk.domain.market import MarketSnapshot

_SNAPSHOT_DEFAULTS: dict[str, Any] = {
    "query": "So11111111111111111111111111111111111111112",
    "chain": "solana",
    "token_address": "So11111111111111111111111111111111111111112",
    "token_symbol": "WSOL",
    "liquidity_usd": 1_000_000.0,
    "age_hours": 5000.0,
    "buys_24h": 1000,
    "sells_24h": 900,
    "source_provider": "dexscreener+helius",
}


@pytest.fixture
def make_snapshot() -> Callable[..., MarketSnapshot]:
    def _factory(**overrides: Any) -> MarketSnapshot:
        return MarketSnapshot(**{**_SNAPSHOT_DEFAULTS, **overrides})

    return _factory


@pytest.fixture
def settings() -> Settings:
    return Settings(model="gpt-4o", temperature=0.0)
