"""Composite provider: market data (primary) + contract data (enricher), merged.

The primary (DexScreener) resolves the query and supplies market fields; the enricher
(Helius) fills the contract fields using the resolved mint. Enrichment is best-effort:
if it fails, the market-only snapshot is returned unchanged, so adding an enricher can
never make the agent *worse* — it only ever adds information.
"""

from __future__ import annotations

import logging

from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import ProviderError
from langley_risk.providers.base import ContractEnricher, DataProvider

logger = logging.getLogger(__name__)


class CompositeProvider:
    """A DataProvider that enriches a primary provider's snapshot with contract data."""

    def __init__(self, primary: DataProvider, enricher: ContractEnricher) -> None:
        self._primary = primary
        self._enricher = enricher

    @property
    def name(self) -> str:
        return f"{self._primary.name}+{self._enricher.name}"

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        snapshot = await self._primary.get_market_snapshot(query)
        try:
            info = await self._enricher.get_contract_info(snapshot.token_address)
        except ProviderError as exc:
            # Best-effort: keep the market-only snapshot rather than fail the analysis.
            logger.warning("Contract enrichment failed for %s: %s", snapshot.token_address, exc)
            return snapshot

        updates = info.contract_updates()
        if not updates:
            return snapshot
        return snapshot.model_copy(update={**updates, "source_provider": self.name})

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._enricher.aclose()
