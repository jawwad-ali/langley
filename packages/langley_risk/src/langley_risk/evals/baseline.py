"""A deterministic, LLM-free baseline scorer.

This is the heuristic the real GPT-4o agent must *beat*. It lets the eval harness,
metrics, and gate run end-to-end with zero OpenAI spend (CI smoke + local demos), and
gives a concrete quality floor. It is NOT a measure of the LLM agent — use the live
eval for that.
"""

from __future__ import annotations

from langley_risk.domain.enums import RiskLevel, SignalCategory, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport
from langley_risk.service.postprocess import has_safety_coverage

LOW_LIQUIDITY_USD = 1_000.0


def _report(
    snapshot: MarketSnapshot,
    *,
    verdict: Verdict,
    confidence: float,
    summary: str,
    signals: list[RiskSignal] | None = None,
    abstain_reason: str | None = None,
) -> TokenRiskReport:
    return TokenRiskReport(
        token_address=snapshot.token_address,
        token_symbol=snapshot.token_symbol,
        verdict=verdict,
        confidence=confidence,
        summary=summary,
        signals=signals or [],
        abstain_reason=abstain_reason,
        data_provider=snapshot.source_provider,
    )


def baseline_report(snapshot: MarketSnapshot) -> TokenRiskReport:
    """Score a snapshot with simple, transparent rules."""
    liq = snapshot.liquidity_usd
    if liq is not None and liq < LOW_LIQUIDITY_USD:
        return _report(
            snapshot,
            verdict=Verdict.LIKELY_UNSAFE,
            confidence=0.8,
            summary="Near-zero liquidity is a strong rug/exit-scam signal.",
            signals=[
                RiskSignal(
                    category=SignalCategory.LIQUIDITY,
                    level=RiskLevel.CRITICAL,
                    title="Negligible liquidity",
                    detail="USD liquidity is below the safety floor.",
                    evidence=[Evidence(field="liquidity_usd", observed_value=str(liq))],
                )
            ],
        )

    if snapshot.buys_24h and snapshot.sells_24h == 0:
        return _report(
            snapshot,
            verdict=Verdict.LIKELY_UNSAFE,
            confidence=0.7,
            summary="Buys with zero sells over 24h is a classic honeypot pattern.",
            signals=[
                RiskSignal(
                    category=SignalCategory.TRADING_ACTIVITY,
                    level=RiskLevel.HIGH,
                    title="One-sided trading (no sells)",
                    detail="Tokens can be bought but not sold.",
                    evidence=[
                        Evidence(field="buys_24h", observed_value=str(snapshot.buys_24h)),
                        Evidence(field="sells_24h", observed_value=str(snapshot.sells_24h)),
                    ],
                )
            ],
        )

    if has_safety_coverage(snapshot):
        return _report(
            snapshot,
            verdict=Verdict.LIKELY_SAFE,
            confidence=0.7,
            summary="Deep liquidity, meaningful age, and two-sided trading observed.",
            signals=[
                RiskSignal(
                    category=SignalCategory.LIQUIDITY,
                    level=RiskLevel.INFO,
                    title="Healthy liquidity, age, and trading",
                    detail="Positive safety signals present across multiple dimensions.",
                    evidence=[
                        Evidence(field="liquidity_usd", observed_value=str(snapshot.liquidity_usd)),
                        Evidence(field="age_hours", observed_value=str(snapshot.age_hours)),
                        Evidence(field="sells_24h", observed_value=str(snapshot.sells_24h)),
                    ],
                )
            ],
        )

    return _report(
        snapshot,
        verdict=Verdict.ABSTAIN,
        confidence=0.5,
        summary="Insufficient evidence to reach a confident verdict.",
        abstain_reason="Available data does not include strong risk or safety signals.",
    )
