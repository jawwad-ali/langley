"""The data-provider abstraction.

A ``DataProvider`` turns a user query (mint address or symbol) into a normalized
``MarketSnapshot``. Anything implementing this Protocol — the live DexScreener
client, a future Helius/Birdeye client, or a fixture-backed provider used in evals
— is interchangeable, so the agent and tools never depend on a concrete source.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from langley_risk.domain.market import MarketSnapshot


class ProviderName(StrEnum):
    """Identifiers for the available data providers."""

    DEXSCREENER = "dexscreener"
    # Future: HELIUS = "helius", BIRDEYE = "birdeye"


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
