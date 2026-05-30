"""Unit tests for the authoritative deterministic gate (defense-in-depth layer C)."""

from __future__ import annotations

from collections.abc import Callable

from langley_risk.domain.enums import RiskLevel, SignalCategory, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport
from langley_risk.service.postprocess import apply_gate, calibrate_confidence


def _report(verdict: Verdict, *, evidence_field: str = "liquidity_usd", confidence: float = 0.9):
    return TokenRiskReport(
        token_address="x",
        verdict=verdict,
        confidence=confidence,
        summary="s",
        signals=[
            RiskSignal(
                category=SignalCategory.LIQUIDITY,
                level=RiskLevel.HIGH,
                title="t",
                detail="d",
                evidence=[Evidence(field=evidence_field, observed_value="123")],
            )
        ],
        data_provider="dexscreener",
    )


class TestEvidenceIntegrity:
    def test_ungrounded_citation_forces_abstain(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # Agent cites holder_count, but the snapshot never had it (None).
        snapshot = make_snapshot(holder_count=None)
        report = _report(Verdict.LIKELY_SAFE, evidence_field="holder_count")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.ABSTAIN
        assert gated.abstain_reason and "not present" in gated.abstain_reason

    def test_grounded_unsafe_verdict_survives(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot(liquidity_usd=10.0)
        report = _report(Verdict.LIKELY_UNSAFE, evidence_field="liquidity_usd")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.LIKELY_UNSAFE

    def test_unsafe_with_mixed_evidence_keeps_verdict_drops_bad_signal(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # Agent flags unsafe with one grounded danger signal + one citing a null field.
        # The gate must KEEP unsafe (conservative) and drop only the ungrounded signal.
        snapshot = make_snapshot(top10_holder_pct=100.0, liquidity_usd=None)
        report = TokenRiskReport(
            token_address="x",
            verdict=Verdict.LIKELY_UNSAFE,
            confidence=0.85,
            summary="concentrated + unknown liquidity",
            signals=[
                RiskSignal(
                    category=SignalCategory.HOLDER_DISTRIBUTION,
                    level=RiskLevel.CRITICAL,
                    title="Extreme concentration",
                    detail="Top holders own everything.",
                    evidence=[Evidence(field="top10_holder_pct", observed_value="100.0")],
                ),
                RiskSignal(
                    category=SignalCategory.LIQUIDITY,
                    level=RiskLevel.HIGH,
                    title="Unknown liquidity",
                    detail="Liquidity not reported.",
                    evidence=[Evidence(field="liquidity_usd", observed_value="None")],
                ),
            ],
            data_provider="dexscreener+helius",
        )
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.LIKELY_UNSAFE
        cited = {e.field for s in gated.signals for e in s.evidence}
        assert cited == {"top10_holder_pct"}  # ungrounded liquidity_usd signal dropped

    def test_unsafe_with_only_ungrounded_evidence_abstains(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot(holder_count=None)
        report = _report(Verdict.LIKELY_UNSAFE, evidence_field="holder_count")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.ABSTAIN


class TestSafetyCoverage:
    def test_likely_safe_without_coverage_forces_abstain(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # Liquidity above the rug floor but below the safe floor, and too new → cannot
        # justify "safe", but also not a hard danger pattern, so the gate abstains.
        snapshot = make_snapshot(liquidity_usd=5_000.0, age_hours=2.0, buys_24h=5, sells_24h=2)
        report = _report(Verdict.LIKELY_SAFE, evidence_field="liquidity_usd")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.ABSTAIN

    def test_likely_safe_with_full_coverage_survives(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot(
            liquidity_usd=500_000.0, age_hours=1000.0, buys_24h=900, sells_24h=800
        )
        report = _report(Verdict.LIKELY_SAFE, evidence_field="liquidity_usd")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.LIKELY_SAFE


class TestDangerOverride:
    def test_honeypot_pattern_forces_unsafe_even_if_agent_abstained(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # Many buys, zero sells → honeypot. Agent abstained; gate must escalate.
        snapshot = make_snapshot(liquidity_usd=8_000.0, age_hours=20.0, buys_24h=137, sells_24h=0)
        report = TokenRiskReport(
            token_address="x",
            verdict=Verdict.ABSTAIN,
            confidence=0.5,
            summary="unsure",
            abstain_reason="not confident",
            data_provider="dexscreener",
        )
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.LIKELY_UNSAFE
        cited = {e.field for s in gated.signals for e in s.evidence}
        assert {"buys_24h", "sells_24h"} <= cited

    def test_rug_liquidity_forces_unsafe_even_if_agent_said_safe(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot(liquidity_usd=12.0)
        report = _report(Verdict.LIKELY_SAFE, evidence_field="liquidity_usd")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.LIKELY_UNSAFE

    def test_healthy_token_is_not_flagged(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # Two-sided trading + deep liquidity → no danger pattern, stays as-is.
        snapshot = make_snapshot(
            liquidity_usd=500_000.0, age_hours=1000.0, buys_24h=900, sells_24h=800
        )
        report = _report(Verdict.LIKELY_SAFE, evidence_field="liquidity_usd")
        gated = apply_gate(report, snapshot)
        assert gated.verdict == Verdict.LIKELY_SAFE


class TestCalibration:
    def test_confidence_is_clamped(self) -> None:
        assert calibrate_confidence(1.4) == 1.0
        assert calibrate_confidence(-0.2) == 0.0
        assert calibrate_confidence(0.7) == 0.7
