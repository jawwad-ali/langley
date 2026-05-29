"""Langley Risk Guardian — evidence-cited Solana token risk assessment.

Public API:
    analyze_token        High-level entrypoint: query -> TokenRiskReport.
    TokenRiskReport      The structured, evidence-cited risk report (agent output).
    RiskSignal, Evidence Components of the report.
    Verdict, RiskLevel   Output enums.
    MarketSnapshot       Provider-neutral market data (agent input).
"""

from __future__ import annotations

from langley_risk.domain.enums import RiskLevel, SignalCategory, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport
from langley_risk.service.analyze import analyze_token

__all__ = [
    "Evidence",
    "MarketSnapshot",
    "RiskLevel",
    "RiskSignal",
    "SignalCategory",
    "TokenRiskReport",
    "Verdict",
    "analyze_token",
]

__version__ = "0.1.0"
