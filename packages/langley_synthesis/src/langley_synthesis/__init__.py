"""Langley Synthesis Orchestrator — fuses specialist agents into one intelligence report.

Public API:
    synthesize_token   Run the specialists + synthesize -> IntelligenceReport.
    IntelligenceReport The fused multi-agent report.
    AgentAgreement     How the specialists' pictures relate.
"""

from __future__ import annotations

from langley_synthesis.domain.enums import AgentAgreement
from langley_synthesis.domain.report import IntelligenceReport, SynthesisOutput
from langley_synthesis.service.orchestrate import synthesize_token

__all__ = [
    "AgentAgreement",
    "IntelligenceReport",
    "SynthesisOutput",
    "synthesize_token",
]

__version__ = "0.1.0"
