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


class TestSafetyCoverage:
    def test_likely_safe_without_coverage_forces_abstain(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # Thin liquidity → cannot justify "safe" even if the citation is grounded.
        snapshot = make_snapshot(liquidity_usd=100.0, age_hours=2.0, buys_24h=5, sells_24h=0)
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


class TestCalibration:
    def test_confidence_is_clamped(self) -> None:
        assert calibrate_confidence(1.4) == 1.0
        assert calibrate_confidence(-0.2) == 0.0
        assert calibrate_confidence(0.7) == 0.7
