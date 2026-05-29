"""Function tools exposed to the Risk Guardian agent.

Tools are deliberately thin: they pull the injected provider off the run context and
delegate. They contain no risk logic — that lives in the agent's reasoning and the
deterministic post-process gate.

On failure they return a terse ``DATA_UNAVAILABLE: ...`` string (via
``failure_error_function``) instead of raising. This is intentional: the model sees a
clear "no data" signal and routes to ABSTAIN rather than hallucinating values.
"""

from __future__ import annotations

import logging

from agents import RunContextWrapper, function_tool

from langley_risk.agents.context import RiskDeps
from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import ProviderError

logger = logging.getLogger(__name__)


def _format_tool_error(ctx: RunContextWrapper[RiskDeps], error: Exception) -> str:
    """Convert a tool exception into a model-visible 'data unavailable' message."""
    if isinstance(error, ProviderError):
        logger.warning("Provider error during tool call: %s", error)
        return f"DATA_UNAVAILABLE: {error}"
    logger.error("Unexpected tool error: %s", error, exc_info=True)
    return "DATA_UNAVAILABLE: an unexpected error occurred while fetching market data"


@function_tool(failure_error_function=_format_tool_error)
async def get_token_market_data(ctx: RunContextWrapper[RiskDeps], query: str) -> MarketSnapshot:
    """Fetch live market, liquidity, and trading data for a Solana token.

    Use this once per analysis to obtain the factual data you must reason over. Every
    claim in your report must cite a field returned by this tool. Fields that come
    back null are genuinely unknown — never assume a value for them.

    Args:
        query: A Solana mint address (e.g. 'So111...') or a token symbol/name to look up.
    """
    return await ctx.context.provider.get_market_snapshot(query)
