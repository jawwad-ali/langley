"""Unit tests for analyze_token wiring (LLM faked — no OpenAI calls)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from langley_risk.config import Settings
from langley_risk.domain.enums import RiskLevel, SignalCategory, Verdict
from langley_risk.domain.market import MarketSnapshot
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport
from langley_risk.service.analyze import analyze_token


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
    def __init__(self, report: TokenRiskReport) -> None:
        self._report = report

    def final_output_as(self, _type: type[Any]) -> TokenRiskReport:
        return self._report


def _safe_report() -> TokenRiskReport:
    return TokenRiskReport(
        token_address="x",
        verdict=Verdict.LIKELY_SAFE,
        confidence=0.9,
        summary="looks fine",
        signals=[
            RiskSignal(
                category=SignalCategory.LIQUIDITY,
                level=RiskLevel.INFO,
                title="liquidity",
                detail="ok",
                evidence=[Evidence(field="liquidity_usd", observed_value="100")],
            )
        ],
        data_provider="stub",
    )


def _patch_runner(monkeypatch: pytest.MonkeyPatch, report: TokenRiskReport, *, fetch: bool) -> None:
    # Read the SDK's keyword args from kwargs to avoid shadowing the `input` builtin.
    async def fake_run(_agent: Any, **kwargs: Any) -> _FakeResult:
        if fetch:
            await kwargs["context"].provider.get_market_snapshot(kwargs["input"])
        return _FakeResult(report)

    monkeypatch.setattr("langley_risk.service.analyze.Runner.run", fake_run)


class TestAnalyzeToken:
    async def test_gate_overrides_unsupported_safe_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        make_snapshot: Callable[..., MarketSnapshot],
        settings: Settings,
    ) -> None:
        # Thin-but-not-rugged token: agent says "likely_safe" but coverage rules can't
        # justify it (above the rug floor, below the safe floor, too new) → abstain.
        snapshot = make_snapshot(liquidity_usd=5_000.0, age_hours=2.0, buys_24h=5, sells_24h=1)
        _patch_runner(monkeypatch, _safe_report(), fetch=True)
        report = await analyze_token("q", provider=_StubProvider(snapshot), settings=settings)
        assert report.verdict == Verdict.ABSTAIN

    async def test_abstains_when_agent_never_fetched_data(
        self,
        monkeypatch: pytest.MonkeyPatch,
        make_snapshot: Callable[..., MarketSnapshot],
        settings: Settings,
    ) -> None:
        snapshot = make_snapshot()
        _patch_runner(monkeypatch, _safe_report(), fetch=False)
        report = await analyze_token("q", provider=_StubProvider(snapshot), settings=settings)
        assert report.verdict == Verdict.ABSTAIN
        assert report.abstain_reason and "No market data" in report.abstain_reason
