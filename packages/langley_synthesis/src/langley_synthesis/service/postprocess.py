"""Deterministic consistency gate for the fused report (no LLM).

The verdict is carried verbatim from the Risk Guardian, but the LLM-authored headline is
free text and could read softer than the verdict warrants. Rather than police the prose
(brittle), this gate ANCHORS the headline to the verdict's stance for any non-safe verdict
— guaranteeing the cautionary stance leads, regardless of the model's wording. This is the
project's rule: never let a confident wrong "safe" impression reach the user.
"""

from __future__ import annotations

from langley_risk.domain.enums import Verdict
from langley_synthesis.domain.report import IntelligenceReport

# Stance prefix for verdicts where a soft headline would be dangerous.
_STANCE: dict[Verdict, str] = {
    Verdict.LIKELY_UNSAFE: "Likely unsafe",
    Verdict.CAUTION: "Caution",
    Verdict.ABSTAIN: "Inconclusive",
}


def enforce_verdict_anchor(report: IntelligenceReport) -> IntelligenceReport:
    """Prefix the headline with the verdict stance for non-safe verdicts."""
    stance = _STANCE.get(report.verdict)
    if stance is None:
        return report  # LIKELY_SAFE: a safe headline under a safe verdict needs no anchor
    if report.headline.lower().startswith(stance.lower()):
        return report  # already leads with the stance
    return report.model_copy(update={"headline": f"{stance} — {report.headline}"})
