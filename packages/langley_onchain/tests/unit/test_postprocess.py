"""Unit tests for the evidence-integrity gate."""

from __future__ import annotations

from collections.abc import Callable

from langley_onchain.domain.enums import ForensicDimension
from langley_onchain.domain.report import Finding, ForensicsReport
from langley_onchain.service.postprocess import apply_integrity
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence


def _finding(dimension: ForensicDimension, field: str) -> Finding:
    return Finding(
        dimension=dimension,
        observation=f"observation citing {field}",
        evidence=[Evidence(field=field, observed_value="123")],
    )


def _report(findings: list[Finding]) -> ForensicsReport:
    return ForensicsReport(
        token_address="x",
        profile_summary="profile",
        findings=findings,
        data_provider="dexscreener+helius",
    )


class TestApplyIntegrity:
    def test_drops_ungrounded_findings_keeps_grounded(
        self, make_snapshot: Callable[..., MarketSnapshot]
    ) -> None:
        # holder_count is None in the snapshot -> that finding is ungrounded and dropped.
        snapshot = make_snapshot(liquidity_usd=1_000_000.0, holder_count=None)
        report = _report(
            [
                _finding(ForensicDimension.LIQUIDITY, "liquidity_usd"),
                _finding(ForensicDimension.HOLDERS, "holder_count"),
            ]
        )
        gated = apply_integrity(report, snapshot)
        kept = {f.dimension for f in gated.findings}
        assert kept == {ForensicDimension.LIQUIDITY}

    def test_all_grounded_unchanged(self, make_snapshot: Callable[..., MarketSnapshot]) -> None:
        snapshot = make_snapshot(liquidity_usd=1_000_000.0, age_hours=5000.0)
        report = _report(
            [
                _finding(ForensicDimension.LIQUIDITY, "liquidity_usd"),
                _finding(ForensicDimension.AGE, "age_hours"),
            ]
        )
        gated = apply_integrity(report, snapshot)
        assert len(gated.findings) == 2
