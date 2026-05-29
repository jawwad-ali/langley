"""Defense-in-depth layer **C**: the authoritative, deterministic gate.

No LLM runs here. Given the agent's report and the exact ``MarketSnapshot`` it was
shown, this module independently enforces the trust invariants and is allowed to
*override* the agent — always in the safe direction (toward ABSTAIN), never toward a
more confident "safe".

It does three things:
1. **Evidence integrity** — every cited field must exist and be non-null in the
   snapshot. An ungrounded citation means the claim was fabricated → force ABSTAIN.
2. **Coverage** — a "likely_safe" verdict requires positive, present safety signals
   (deep liquidity, meaningful age, two-sided trading). Absence of red flags is not
   safety → force ABSTAIN.
3. **Calibration** — clamp/normalize the model's self-reported confidence (v1 is a
   clamp; a fitted mapping can replace ``calibrate_confidence`` later).
"""

from __future__ import annotations

import logging

from langley_risk.domain.enums import CONCLUSIVE_VERDICTS, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import TokenRiskReport

logger = logging.getLogger(__name__)

# Thresholds that gate a "likely_safe" verdict. Conservative on purpose.
MIN_SAFE_LIQUIDITY_USD = 50_000.0
MIN_SAFE_AGE_HOURS = 168.0  # 7 days
ABSTAIN_CONFIDENCE_CAP = 0.6


def calibrate_confidence(raw: float) -> float:
    """Map the model's self-reported confidence to a calibrated value.

    v1: clamp to [0, 1]. Replace with a fitted isotonic/Platt mapping once enough
    eval data exists, without touching callers.
    """
    return max(0.0, min(1.0, raw))


def _force_abstain(report: TokenRiskReport, reason: str) -> TokenRiskReport:
    """Return a copy of ``report`` overridden to ABSTAIN, preserving signals."""
    logger.info("Gate forcing ABSTAIN for %s: %s", report.token_address, reason)
    return report.model_copy(
        update={
            "verdict": Verdict.ABSTAIN,
            "abstain_reason": reason,
            "confidence": min(calibrate_confidence(report.confidence), ABSTAIN_CONFIDENCE_CAP),
        }
    )


def _ungrounded_fields(report: TokenRiskReport, snapshot: MarketSnapshot) -> list[str]:
    """Return cited evidence fields that are not present/non-null in the snapshot."""
    citable = snapshot.citable_fields()
    cited = {ev.field for signal in report.signals for ev in signal.evidence}
    return sorted(cited - citable)


def evidence_is_grounded(report: TokenRiskReport, snapshot: MarketSnapshot) -> bool:
    """Whether every cited field exists and is non-null in the snapshot."""
    return not _ungrounded_fields(report, snapshot)


def has_safety_coverage(snapshot: MarketSnapshot) -> bool:
    """Whether the snapshot carries enough positive evidence to justify 'likely_safe'."""
    if snapshot.liquidity_usd is None or snapshot.liquidity_usd < MIN_SAFE_LIQUIDITY_USD:
        return False
    if snapshot.age_hours is None or snapshot.age_hours < MIN_SAFE_AGE_HOURS:
        return False
    # Two-sided trading: both buys and sells observed, with at least some sells.
    return not (snapshot.buys_24h is None or snapshot.sells_24h is None or snapshot.sells_24h <= 0)


def apply_gate(report: TokenRiskReport, snapshot: MarketSnapshot) -> TokenRiskReport:
    """Run the deterministic gate; return a (possibly overridden) report."""
    # 1. Evidence integrity — applies to any conclusive verdict.
    if report.verdict in CONCLUSIVE_VERDICTS:
        ungrounded = _ungrounded_fields(report, snapshot)
        if ungrounded:
            return _force_abstain(
                report,
                f"Verdict cited fields not present in the data: {', '.join(ungrounded)}. "
                "Conclusion was not grounded in observed values.",
            )

    # 2. Coverage — a 'likely_safe' claim needs positive, present safety signals.
    if report.verdict == Verdict.LIKELY_SAFE and not has_safety_coverage(snapshot):
        return _force_abstain(
            report,
            "Insufficient positive safety evidence (need deep liquidity, meaningful age, "
            "and two-sided trading present). Absence of red flags is not proof of safety.",
        )

    # 3. Calibration — normalize confidence for verdicts that survive the gate.
    calibrated = calibrate_confidence(report.confidence)
    if calibrated != report.confidence:
        return report.model_copy(update={"confidence": calibrated})
    return report
