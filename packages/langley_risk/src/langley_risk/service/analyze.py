"""``analyze_token`` — the high-level entrypoint used by the CLI, future API, and evals.

It runs the agent, captures the *exact* snapshot the agent's tool returned (via a
recording wrapper, so there is a single network call and the gate sees precisely what
the model saw), then applies the deterministic post-process gate.
"""

from __future__ import annotations

import logging
import uuid

from agents import RunConfig, Runner
from agents.exceptions import AgentsException
from openai import OpenAIError

from langley_risk.agents.context import RiskDeps
from langley_risk.agents.risk_guardian import build_risk_guardian
from langley_risk.config import Settings, get_settings
from langley_risk.domain.enums import Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import TokenRiskReport
from langley_risk.errors import AgentError
from langley_risk.providers.base import DataProvider
from langley_risk.providers.factory import get_provider
from langley_risk.service.postprocess import apply_gate

logger = logging.getLogger(__name__)


class _RecordingProvider:
    """Wraps a provider and remembers the last snapshot it returned.

    Lets the service feed the agent and the gate the same data from one fetch.
    """

    def __init__(self, inner: DataProvider) -> None:
        self._inner = inner
        self.last_snapshot: MarketSnapshot | None = None

    @property
    def name(self) -> str:
        return self._inner.name

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        snapshot = await self._inner.get_market_snapshot(query)
        self.last_snapshot = snapshot
        return snapshot

    async def aclose(self) -> None:
        await self._inner.aclose()


async def analyze_token(
    query: str,
    *,
    provider: DataProvider | None = None,
    settings: Settings | None = None,
) -> TokenRiskReport:
    """Assess the risk of a Solana token.

    Args:
        query: A Solana mint address or token symbol/name.
        provider: Optional data provider; if omitted, one is built from settings and
            closed automatically. If supplied, the caller owns its lifecycle.
        settings: Optional settings; defaults to the process settings.

    Returns:
        A gated ``TokenRiskReport``.

    Raises:
        AgentError: The agent run failed.
    """
    settings = settings or get_settings()
    owns_provider = provider is None
    inner = provider or get_provider(settings)
    recorder = _RecordingProvider(inner)
    run_id = uuid.uuid4().hex

    deps = RiskDeps(provider=recorder, settings=settings, run_id=run_id)
    agent = build_risk_guardian(settings)

    try:
        result = await Runner.run(
            agent,
            input=query,
            context=deps,
            max_turns=settings.max_turns,
            run_config=RunConfig(
                workflow_name="risk_guardian.analyze",
                trace_metadata={"run_id": run_id, "query": query},
            ),
        )
        report = result.final_output_as(TokenRiskReport)
    except (AgentsException, OpenAIError) as exc:
        raise AgentError(f"Risk Guardian run failed for {query!r}: {exc}") from exc
    finally:
        if owns_provider:
            await recorder.aclose()

    snapshot = recorder.last_snapshot
    if snapshot is None:
        logger.warning("Agent produced a report without fetching data for %s", query)
        return report.model_copy(
            update={
                "verdict": Verdict.ABSTAIN,
                "abstain_reason": "No market data was retrieved, so no verdict can be grounded.",
            }
        )

    return apply_gate(report, snapshot)
