"""Unit tests for analyze_onchain wiring (LLM faked — no OpenAI calls)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from langley_onchain.domain.enums import ForensicDimension
from langley_onchain.domain.report import Finding, ForensicsReport
from langley_onchain.service.analyze import analyze_onchain
from langley_risk.config import Settings
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence


class _StubProvider:
    def __init__(self, snapshot: MarketSnapshot) -> None:
        self._snapshot = snapshot

    @property
    def name(self) -> str:
        return "stub"

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        return self._snapshot

    async def aclose(self) -> None:
        return None


class _FakeResult:
    def __init__(self, report: ForensicsReport) -> None:
        self._report = report

    def final_output_as(self, _type: type[Any]) -> ForensicsReport:
        return self._report


def _report(field: str) -> ForensicsReport:
    return ForensicsReport(
        token_address="x",
        profile_summary="profile",
        findings=[
            Finding(
                dimension=ForensicDimension.HOLDERS,
                observation="cites a field",
                evidence=[Evidence(field=field, observed_value="1")],
            )
        ],
        data_provider="stub",
    )


def _patch_runner(monkeypatch: pytest.MonkeyPatch, report: ForensicsReport, *, fetch: bool) -> None:
    async def fake_run(_agent: Any, **kwargs: Any) -> _FakeResult:
        if fetch:
            await kwargs["context"].provider.get_market_snapshot(kwargs["input"])
        return _FakeResult(report)

    monkeypatch.setattr("langley_onchain.service.analyze.Runner.run", fake_run)


class TestAnalyzeOnchain:
    async def test_gate_drops_ungrounded_finding(
        self,
        monkeypatch: pytest.MonkeyPatch,
        make_snapshot: Callable[..., MarketSnapshot],
        settings: Settings,
    ) -> None:
        snapshot = make_snapshot(holder_count=None)  # finding cites holder_count -> dropped
        _patch_runner(monkeypatch, _report("holder_count"), fetch=True)
        report = await analyze_onchain("q", provider=_StubProvider(snapshot), settings=settings)
        assert report.findings == []

    async def test_empty_profile_when_no_data_fetched(
        self,
        monkeypatch: pytest.MonkeyPatch,
        make_snapshot: Callable[..., MarketSnapshot],
        settings: Settings,
    ) -> None:
        _patch_runner(monkeypatch, _report("liquidity_usd"), fetch=False)
        report = await analyze_onchain(
            "q", provider=_StubProvider(make_snapshot()), settings=settings
        )
        assert report.findings == []
        assert "No on-chain" in report.profile_summary
