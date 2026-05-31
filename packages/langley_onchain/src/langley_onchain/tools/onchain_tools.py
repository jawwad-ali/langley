"""Function tool exposing the reused data provider to the Forensics agent.

Thin by design: it pulls the injected provider off the run context and delegates. On
failure it returns ``DATA_UNAVAILABLE: ...`` so the model reports an empty/insufficient
profile rather than inventing facts.
"""

from __future__ import annotations

import logging

from agents import RunContextWrapper, function_tool

from langley_onchain.agents.context import ForensicsDeps
from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import ProviderError, TokenNotFoundError

logger = logging.getLogger(__name__)


def _format_tool_error(ctx: RunContextWrapper[ForensicsDeps], error: Exception) -> str:
    """Convert a tool exception into a model-visible 'data unavailable' message."""
    if isinstance(error, TokenNotFoundError):
        logger.info("Token not found during forensics tool call: %s", error)
        return f"DATA_UNAVAILABLE: no token or pair was found for {error.query!r}"
    if isinstance(error, ProviderError):
        logger.warning("Provider error during forensics tool call: %s", error)
        return f"DATA_UNAVAILABLE: {error}"
    logger.error("Unexpected forensics tool error: %s", error, exc_info=True)
    return "DATA_UNAVAILABLE: an unexpected error occurred while fetching on-chain data"


@function_tool(failure_error_function=_format_tool_error)
async def get_onchain_snapshot(ctx: RunContextWrapper[ForensicsDeps], query: str) -> MarketSnapshot:
    """Fetch on-chain + market data for a Solana token to build a forensic profile.

    Call this once. Every observation in your report must cite a field it returns; fields
    that come back null are genuinely unknown — omit those dimensions.

    Args:
        query: A Solana mint address (e.g. 'So111...') or a token symbol/name to look up.
    """
    return await ctx.context.provider.get_market_snapshot(query)
