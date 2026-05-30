"""Unit tests for CompositeProvider: merge contract data + graceful degradation."""

from __future__ import annotations

from collections.abc import Callable

from langley_risk.domain.contract import ContractInfo
from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import ProviderTimeoutError
from langley_risk.providers.composite import CompositeProvider


class _StubPrimary:
    def __init__(self, snapshot: MarketSnapshot) -> None:
        self._snapshot = snapshot

    @property
    def name(self) -> str:
        return "dexscreener"

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        return self._snapshot

    async def aclose(self) -> None:
        return None


class _StubEnricher:
    def __init__(self, info: ContractInfo | None = None, *, fail: bool = False) -> None:
        self._info = info
        self._fail = fail

    @property
    def name(self) -> str:
        return "helius"

    async def get_contract_info(self, mint: str) -> ContractInfo:
        if self._fail:
            raise ProviderTimeoutError("helius")
        assert self._info is not None
        return self._info

    async def aclose(self) -> None:
        return None


class TestCompositeProvider:
    async def test_merges_contract_fields_into_snapshot(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot(mint_authority_renounced=None, top10_holder_pct=None)
        info = ContractInfo(
            mint_authority_renounced=False,
            top10_holder_pct=92.0,
            source_provider="helius",
        )
        composite = CompositeProvider(_StubPrimary(snapshot), _StubEnricher(info))
        result = await composite.get_market_snapshot("q")
        assert result.mint_authority_renounced is False
        assert result.top10_holder_pct == 92.0
        assert result.source_provider == "dexscreener+helius"
        # Market fields are preserved from the primary.
        assert result.liquidity_usd == snapshot.liquidity_usd

    async def test_enrichment_failure_degrades_to_market_only(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot()
        composite = CompositeProvider(_StubPrimary(snapshot), _StubEnricher(fail=True))
        result = await composite.get_market_snapshot("q")
        # Unchanged: enrichment never makes the analysis worse.
        assert result == snapshot
        assert result.source_provider == "dexscreener"
