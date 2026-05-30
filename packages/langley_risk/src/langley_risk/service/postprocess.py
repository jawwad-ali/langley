"""Defense-in-depth layer **C**: the authoritative, deterministic gate.

No LLM runs here. Given the agent's report and the exact ``MarketSnapshot`` it was
shown, this module independently enforces the trust invariants and is allowed to
*override* the agent — never toward a more confident "safe", but it WILL escalate to
ABSTAIN or LIKELY_UNSAFE when the data demands it.

It does four things:
1. **Danger override** — hard, unambiguous danger patterns (near-zero liquidity rug;
   buys-with-zero-sells honeypot) force LIKELY_UNSAFE if the agent failed to flag them.
   This is the safety net for missed scams.
2. **Evidence integrity** — every cited field must exist and be non-null in the
   snapshot. An ungrounded citation means the claim was fabricated → force ABSTAIN.
3. **Coverage** — a "likely_safe" verdict requires positive, present safety signals
   (deep liquidity, meaningful age, two-sided trading). Absence of red flags is not
   safety → force ABSTAIN.
4. **Calibration** — clamp/normalize the model's self-reported confidence (v1 is a
   clamp; a fitted mapping can replace ``calibrate_confidence`` later).
"""

from __future__ import annotations

import logging

from langley_risk.domain.enums import CONCLUSIVE_VERDICTS, RiskLevel, SignalCategory, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport

logger = logging.getLogger(__name__)

# Thresholds that gate a "likely_safe" verdict. Conservative on purpose.
MIN_SAFE_LIQUIDITY_USD = 50_000.0
MIN_SAFE_AGE_HOURS = 168.0  # 7 days
ABSTAIN_CONFIDENCE_CAP = 0.6

# Thresholds for the hard danger override (escalate to LIKELY_UNSAFE).
RUG_MAX_LIQUIDITY_USD = 1_000.0
HONEYPOT_MIN_BUYS = 20
DANGER_CONFIDENCE = 0.85


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


def _danger_signal(snapshot: MarketSnapshot) -> RiskSignal | None:
    """Return a grounded danger signal if the data shows a hard scam pattern, else None."""
    liq = snapshot.liquidity_usd
    if liq is not None and liq < RUG_MAX_LIQUIDITY_USD:
        return RiskSignal(
            category=SignalCategory.LIQUIDITY,
            level=RiskLevel.CRITICAL,
            title="Negligible liquidity",
            detail="USD liquidity is below the rug-risk floor; exit may be impossible.",
            evidence=[Evidence(field="liquidity_usd", observed_value=str(liq))],
        )
    if (
        snapshot.buys_24h is not None
        and snapshot.buys_24h > HONEYPOT_MIN_BUYS
        and (snapshot.sells_24h == 0)
    ):
        return RiskSignal(
            category=SignalCategory.TRADING_ACTIVITY,
            level=RiskLevel.CRITICAL,
            title="One-sided trading (no sells)",
            detail="Meaningful buys with zero sells in 24h — classic honeypot pattern.",
            evidence=[
                Evidence(field="buys_24h", observed_value=str(snapshot.buys_24h)),
                Evidence(field="sells_24h", observed_value=str(snapshot.sells_24h)),
            ],
        )
    return None


def _force_unsafe(report: TokenRiskReport, signal: RiskSignal) -> TokenRiskReport:
    """Override ``report`` to LIKELY_UNSAFE with a grounded danger signal."""
    logger.info("Gate forcing LIKELY_UNSAFE for %s: %s", report.token_address, signal.title)
    return report.model_copy(
        update={
            "verdict": Verdict.LIKELY_UNSAFE,
            "abstain_reason": None,
            "confidence": DANGER_CONFIDENCE,
            "summary": f"Hard danger pattern detected: {signal.detail}",
            "signals": [signal],
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


def _grounded_signals(report: TokenRiskReport, snapshot: MarketSnapshot) -> list[RiskSignal]:
    """Signals whose every cited field is present (non-null) in the snapshot."""
    citable = snapshot.citable_fields()
    return [
        s for s in report.signals if s.evidence and all(ev.field in citable for ev in s.evidence)
    ]


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
    # 0. Danger override — if the data shows a hard scam pattern the agent did NOT
    #    already flag as unsafe, escalate to LIKELY_UNSAFE with grounded evidence.
    if report.verdict != Verdict.LIKELY_UNSAFE:
        danger = _danger_signal(snapshot)
        if danger is not None:
            return _force_unsafe(report, danger)

    # 1. Evidence integrity. Ungrounded citations may not JUSTIFY a verdict, but the gate
    #    must never move a verdict AWAY from caution. So:
    #    - LIKELY_UNSAFE: drop the ungrounded signals but KEEP the verdict as long as a
    #      grounded danger signal remains (forcing abstain here would be less safe). Only
    #      if NO signal is grounded is the danger fabricated -> abstain.
    #    - safe / caution: any ungrounded citation -> abstain (don't trust it).
    if report.verdict in CONCLUSIVE_VERDICTS:
        grounded = _grounded_signals(report, snapshot)
        if len(grounded) != len(report.signals):
            if report.verdict == Verdict.LIKELY_UNSAFE and grounded:
                report = report.model_copy(update={"signals": grounded})
            else:
                return _force_abstain(
                    report,
                    "Verdict cited fields not present in the observed data; not grounded.",
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
