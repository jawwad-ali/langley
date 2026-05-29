"""Unit tests for the domain output contract and its invariants."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from langley_risk.domain.enums import RiskLevel, SignalCategory, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport


def _signal() -> RiskSignal:
    return RiskSignal(
        category=SignalCategory.LIQUIDITY,
        level=RiskLevel.CRITICAL,
        title="Negligible liquidity",
        detail="USD liquidity is near zero.",
        evidence=[Evidence(field="liquidity_usd", observed_value="12.5")],
    )


class TestTokenRiskReportInvariants:
    def test_abstain_requires_reason(self) -> None:
        with pytest.raises(ValidationError, match="abstain_reason"):
            TokenRiskReport(
                token_address="x",
                verdict=Verdict.ABSTAIN,
                confidence=0.5,
                summary="no call",
                data_provider="dexscreener",
            )

    def test_abstain_with_reason_is_valid(self) -> None:
        report = TokenRiskReport(
            token_address="x",
            verdict=Verdict.ABSTAIN,
            confidence=0.5,
            summary="no call",
            abstain_reason="insufficient data",
            data_provider="dexscreener",
        )
        assert report.verdict == Verdict.ABSTAIN

    def test_conclusive_verdict_requires_a_signal(self) -> None:
        with pytest.raises(ValidationError, match="at least one risk signal"):
            TokenRiskReport(
                token_address="x",
                verdict=Verdict.LIKELY_UNSAFE,
                confidence=0.8,
                summary="bad",
                signals=[],
                data_provider="dexscreener",
            )

    def test_conclusive_verdict_with_evidenced_signal_is_valid(self) -> None:
        report = TokenRiskReport(
            token_address="x",
            verdict=Verdict.LIKELY_UNSAFE,
            confidence=0.8,
            summary="bad",
            signals=[_signal()],
            data_provider="dexscreener",
        )
        assert report.signals[0].evidence[0].field == "liquidity_usd"

    def test_confidence_must_be_in_range(self) -> None:
        with pytest.raises(ValidationError):
            TokenRiskReport(
                token_address="x",
                verdict=Verdict.ABSTAIN,
                confidence=1.5,
                summary="x",
                abstain_reason="r",
                data_provider="dexscreener",
            )


class TestCitableFields:
    def test_only_non_null_fields_are_citable(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        snapshot = make_snapshot(holder_count=None, liquidity_usd=1000.0)
        citable = snapshot.citable_fields()
        assert "liquidity_usd" in citable
        assert "holder_count" not in citable
