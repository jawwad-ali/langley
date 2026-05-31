"""``analyze_onchain`` — the entrypoint used by the CLI, future API, and orchestrator.

Runs the Forensics agent, captures the exact snapshot its tool returned (one fetch,
shared with the gate), then applies the evidence-integrity gate. Mirrors the Risk
Guardian's ``analyze_token`` and reuses langley_risk's provider/config/errors.
"""

from __future__ import annotations

import logging
import uuid

from agents import RunConfig, Runner
from agents.exceptions import AgentsException
from openai import OpenAIError
from pydantic import ValidationError

from langley_onchain.agents.context import ForensicsDeps
from langley_onchain.agents.forensics import build_forensics_agent
from langley_onchain.domain.report import ForensicsReport
from langley_onchain.service.postprocess import apply_integrity
from langley_risk.config import Settings, get_settings
from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import AgentError
from langley_risk.providers.base import DataProvider
from langley_risk.providers.factory import get_provider

logger = logging.getLogger(__name__)


class _RecordingProvider(DataProvider):
    """Wraps a provider and remembers the last snapshot, so agent and gate share one fetch."""

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


async def analyze_onchain(
    query: str,
    *,
    provider: DataProvider | None = None,
    settings: Settings | None = None,
) -> ForensicsReport:
    """Produce a neutral, evidence-cited on-chain forensic profile of a token.

    Args:
        query: A Solana mint address or token symbol/name.
        provider: Optional data provider; built from settings and auto-closed if omitted.
        settings: Optional settings; defaults to the process settings.

    Raises:
        AgentError: The agent run failed.
    """
    settings = settings or get_settings()
    owns_provider = provider is None
    inner = provider or get_provider(settings)
    recorder = _RecordingProvider(inner)
    run_id = uuid.uuid4().hex

    deps = ForensicsDeps(provider=recorder, settings=settings, run_id=run_id)
    agent = build_forensics_agent(settings)

    try:
        result = await Runner.run(
            agent,
            input=query,
            context=deps,
            max_turns=settings.max_turns,
            run_config=RunConfig(
                workflow_name="onchain_forensics.analyze",
                trace_metadata={"run_id": run_id, "query": query},
            ),
        )
        report = result.final_output_as(ForensicsReport)
    except (AgentsException, OpenAIError, ValidationError) as exc:
        raise AgentError(f"On-Chain Forensics run failed for {query!r}: {exc}") from exc
    finally:
        if owns_provider:
            await recorder.aclose()

    snapshot = recorder.last_snapshot
    if snapshot is None:
        logger.warning("Forensics produced a profile without fetching data for %s", query)
        return report.model_copy(
            update={
                "findings": [],
                "profile_summary": "No on-chain or market data was retrieved for this token.",
                "token_address": query,
                "token_symbol": None,
                "data_provider": recorder.name,
            }
        )
    # Stamp identity + provenance from the actual data, never the model's output.
    grounded = report.model_copy(
        update={
            "token_address": snapshot.token_address,
            "token_symbol": snapshot.token_symbol,
            "data_provider": recorder.name,
        }
    )
    return apply_integrity(grounded, snapshot)
