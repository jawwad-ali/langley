"""``synthesize_token`` — the multi-agent orchestration entrypoint.

Runs the Risk Guardian and On-Chain Forensics specialists concurrently, then runs the
synthesis agent over their outputs, and assembles a unified ``IntelligenceReport``.

Trust guarantee: the report's ``verdict`` and ``confidence`` are carried VERBATIM from
the Risk Guardian. The synthesis LLM only contributes narrative/cross-analysis, so it can
never decide or weaken the safety call.
"""

from __future__ import annotations

import asyncio
import logging

from agents import RunConfig, Runner
from agents.exceptions import AgentsException
from openai import OpenAIError
from pydantic import ValidationError

from langley_onchain.domain.report import ForensicsReport
from langley_onchain.service.analyze import analyze_onchain
from langley_risk.config import Settings, get_settings
from langley_risk.domain.report import TokenRiskReport
from langley_risk.errors import AgentError
from langley_risk.service.analyze import analyze_token
from langley_synthesis.agents.synthesizer import build_synthesizer
from langley_synthesis.domain.report import IntelligenceReport, SynthesisOutput
from langley_synthesis.service.postprocess import enforce_verdict_anchor

logger = logging.getLogger(__name__)


def _serialize(risk: TokenRiskReport, forensics: ForensicsReport | None) -> str:
    """Render the two specialist reports into the synthesizer's input."""
    lines = [
        "RISK GUARDIAN (authoritative safety verdict):",
        f"  verdict: {risk.verdict.value}",
        f"  confidence: {risk.confidence:.2f}",
        f"  summary: {risk.summary}",
    ]
    if risk.signals:
        lines.append("  signals:")
        lines += [
            f"    - [{s.level.value}] {s.category.value}: {s.title} — {s.detail}"
            for s in risk.signals
        ]
    lines.append("")
    if forensics and forensics.findings:
        lines.append("ON-CHAIN FORENSICS (neutral profile):")
        lines.append(f"  summary: {forensics.profile_summary}")
        lines.append("  findings:")
        lines += [f"    - [{f.dimension.value}] {f.observation}" for f in forensics.findings]
    else:
        lines.append("ON-CHAIN FORENSICS: unavailable (no profile produced).")
    return "\n".join(lines)


async def _run_synthesizer(
    query: str, risk: TokenRiskReport, forensics: ForensicsReport | None, settings: Settings
) -> SynthesisOutput:
    agent = build_synthesizer(settings)
    try:
        result = await Runner.run(
            agent,
            input=_serialize(risk, forensics),
            max_turns=2,
            run_config=RunConfig(workflow_name="synthesis.fuse", trace_metadata={"query": query}),
        )
        return result.final_output_as(SynthesisOutput)
    except (AgentsException, OpenAIError, ValidationError) as exc:
        raise AgentError(f"Synthesis run failed for {query!r}: {exc}") from exc


def _assemble(
    risk: TokenRiskReport, forensics: ForensicsReport | None, synthesis: SynthesisOutput
) -> IntelligenceReport:
    # Identity must be the token the VERDICT pertains to (the Risk Guardian's). If forensics
    # resolved a different mint (Solana symbol collisions), trust the risk address and warn —
    # never attribute the verdict to a different token.
    token_address = risk.token_address
    token_symbol = risk.token_symbol
    if forensics and forensics.token_address != risk.token_address:
        logger.warning(
            "Specialist identity mismatch (risk=%s forensics=%s); using risk address",
            risk.token_address,
            forensics.token_address,
        )
    elif forensics:
        token_symbol = forensics.token_symbol or risk.token_symbol
    contributing = ["risk_guardian"] + (["onchain_forensics"] if forensics else [])
    return IntelligenceReport(
        token_address=token_address,
        token_symbol=token_symbol,
        verdict=risk.verdict,  # carried verbatim — authoritative
        confidence=risk.confidence,
        headline=synthesis.headline,
        briefing=synthesis.briefing,
        agreement=synthesis.agreement,
        key_points=synthesis.key_points,
        risk_signals=risk.signals,
        forensic_findings=forensics.findings if forensics else [],
        contributing_agents=contributing,
        data_provider=risk.data_provider,
    )


async def synthesize_token(query: str, *, settings: Settings | None = None) -> IntelligenceReport:
    """Run the specialists, synthesize, and return a unified intelligence report.

    Raises:
        AgentError: The Risk Guardian (the essential safety call) or the synthesizer failed.
    """
    settings = settings or get_settings()
    risk_res, forensics_res = await asyncio.gather(
        analyze_token(query, settings=settings),
        analyze_onchain(query, settings=settings),
        return_exceptions=True,
    )

    # Never swallow cancellation/interrupt — re-raise so cooperative cancellation works.
    for res in (risk_res, forensics_res):
        if isinstance(res, (asyncio.CancelledError, KeyboardInterrupt)):
            raise res

    if isinstance(risk_res, BaseException):
        raise AgentError(f"Risk Guardian failed for {query!r}: {risk_res}") from risk_res
    risk: TokenRiskReport = risk_res

    forensics: ForensicsReport | None = None
    if isinstance(forensics_res, ForensicsReport):
        forensics = forensics_res
    else:
        logger.warning("On-Chain Forensics unavailable for %s: %s", query, forensics_res)

    synthesis = await _run_synthesizer(query, risk, forensics, settings)
    return enforce_verdict_anchor(_assemble(risk, forensics, synthesis))
