"""The data-provider abstraction.

A ``DataProvider`` turns a user query (mint address or symbol) into a normalized
``MarketSnapshot``. Anything implementing this Protocol — the live DexScreener
client, a future Helius/Birdeye client, or a fixture-backed provider used in evals
— is interchangeable, so the agent and tools never depend on a concrete source.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from langley_risk.domain.contract import ContractInfo
from langley_risk.domain.market import MarketSnapshot


class ProviderName(StrEnum):
    """Identifiers for the available data providers / enrichers."""

    DEXSCREENER = "dexscreener"
    # "helius" and "composite" both resolve to DexScreener market data enriched with
    # Helius contract data (Helius alone has no market/liquidity view).
    HELIUS = "helius"
    COMPOSITE = "composite"
    # Future: BIRDEYE = "birdeye"


@runtime_checkable
class DataProvider(Protocol):
    """Fetches normalized market data for a token.

    Implementations must map provider-specific failures onto the
    ``langley_risk.errors.ProviderError`` hierarchy so the agent can distinguish
    "not found" from "source unavailable" and abstain appropriately.
    """

    @property
    def name(self) -> str:
        """Human-readable provider name, recorded in the snapshot's provenance."""
        ...

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        """Return a ``MarketSnapshot`` for ``query``.

        Raises:
            TokenNotFoundError: No token/pair matches the query.
            ProviderRateLimitedError: The provider rate-limited the request.
            ProviderTimeoutError: The provider did not respond in time.
            ProviderResponseInvalidError: The response could not be parsed.
        """
        ...

    async def aclose(self) -> None:
        """Release any underlying resources (e.g. HTTP connections)."""
        ...


@runtime_checkable
class ContractEnricher(Protocol):
    """Fetches contract-level facts for a mint that a market provider cannot see.

    Used additively by ``CompositeProvider`` to fill the contract fields of a
    ``MarketSnapshot``. Failures must raise the ``ProviderError`` hierarchy so the
    composite can degrade gracefully (keep the market-only snapshot).
    """

    @property
    def name(self) -> str:
        """Human-readable enricher name."""
        ...

    async def get_contract_info(self, mint: str) -> ContractInfo:
        """Return contract-level signals for a Solana mint address."""
        ...

    async def aclose(self) -> None:
        """Release any underlying resources (e.g. HTTP connections)."""
        ...
