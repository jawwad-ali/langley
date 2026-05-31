"""Langley On-Chain Forensics — neutral, evidence-cited on-chain profile of a token.

Public API:
    analyze_onchain   High-level entrypoint: query -> ForensicsReport.
    ForensicsReport   The neutral forensic profile (agent output).
    Finding           A single evidence-cited observation.
    ForensicDimension Output enum.
"""

from __future__ import annotations

from langley_onchain.domain.enums import ForensicDimension
from langley_onchain.domain.report import Finding, ForensicsReport
from langley_onchain.service.analyze import analyze_onchain

__all__ = [
    "Finding",
    "ForensicDimension",
    "ForensicsReport",
    "analyze_onchain",
]

__version__ = "0.1.0"
