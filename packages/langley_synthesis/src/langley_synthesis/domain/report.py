"""Synthesis output contracts.

Two models, deliberately separated for trust:

- ``SynthesisOutput`` is what the synthesis LLM is allowed to produce — narrative and
  cross-analysis ONLY (headline, briefing, agreement, key points). It cannot contain a
  verdict or confidence, so the LLM structurally cannot decide the safety call.
- ``IntelligenceReport`` is the final fused report the orchestrator ASSEMBLES. Its
  ``verdict`` and ``confidence`` are carried verbatim from the Risk Guardian (the
  authoritative safety call); the synthesis fields come from ``SynthesisOutput``; the
  underlying signals/findings come from the two specialists.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from langley_onchain.domain.report import Finding
from langley_risk.domain.enums import Verdict
from langley_risk.domain.report import RiskSignal
from langley_synthesis.domain.enums import AgentAgreement


def _empty_str_list() -> list[str]:
    return []


def _empty_signals() -> list[RiskSignal]:
    return []


def _empty_findings() -> list[Finding]:
    return []


class SynthesisOutput(BaseModel):
    """Narrative + cross-analysis from the synthesis LLM. Contains NO verdict by design."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=160)
    briefing: str = Field(min_length=1, max_length=900)
    agreement: AgentAgreement
    key_points: list[str] = Field(default_factory=_empty_str_list)


class IntelligenceReport(BaseModel):
    """The fused, multi-agent intelligence report (assembled by the orchestrator)."""

    model_config = ConfigDict(extra="forbid")

    token_address: str
    token_symbol: str | None = None

    # Authoritative safety call — carried VERBATIM from the Risk Guardian, never the LLM.
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)

    # Synthesis (narrative / cross-analysis only).
    headline: str
    briefing: str
    agreement: AgentAgreement
    key_points: list[str] = Field(default_factory=_empty_str_list)

    # Underlying specialist detail (provenance).
    risk_signals: list[RiskSignal] = Field(default_factory=_empty_signals)
    forensic_findings: list[Finding] = Field(default_factory=_empty_findings)
    contributing_agents: list[str] = Field(default_factory=_empty_str_list)
    data_provider: str
