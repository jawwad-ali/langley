"""Unit tests for the ForensicsReport output contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from langley_onchain.domain.enums import ForensicDimension
from langley_onchain.domain.report import Finding, ForensicsReport
from langley_risk.domain.report import Evidence


def _finding(field: str = "liquidity_usd") -> Finding:
    return Finding(
        dimension=ForensicDimension.LIQUIDITY,
        observation="USD liquidity is deep.",
        evidence=[Evidence(field=field, observed_value="1000000.0")],
    )


class TestForensicsReport:
    def test_valid_report_with_evidenced_findings(self) -> None:
        report = ForensicsReport(
            token_address="x",
            profile_summary="Mature token with deep liquidity and active trading.",
            findings=[_finding()],
            data_provider="dexscreener+helius",
        )
        assert report.findings[0].evidence[0].field == "liquidity_usd"

    def test_report_with_no_findings_is_allowed(self) -> None:
        # An empty profile (e.g. no data) is valid as long as the summary explains it.
        report = ForensicsReport(
            token_address="x",
            profile_summary="No data was available.",
            data_provider="dexscreener",
        )
        assert report.findings == []

    def test_finding_without_evidence_is_rejected(self) -> None:
        bad = Finding.model_construct(
            dimension=ForensicDimension.AGE, observation="old", evidence=[]
        )
        with pytest.raises(ValidationError, match="must cite data"):
            ForensicsReport(
                token_address="x",
                profile_summary="s",
                findings=[bad],
                data_provider="dexscreener",
            )
