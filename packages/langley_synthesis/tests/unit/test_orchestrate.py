"""Unit tests for the orchestrator (specialists + synthesizer all faked — no OpenAI)."""

from __future__ import annotations

from typing import Any

import pytest

from langley_onchain.domain.enums import ForensicDimension
from langley_onchain.domain.report import Finding, ForensicsReport
from langley_risk.domain.enums import RiskLevel, SignalCategory, Verdict
from langley_risk.domain.report import Evidence, RiskSignal, TokenRiskReport
from langley_synthesis.domain.enums import AgentAgreement
from langley_synthesis.domain.report import SynthesisOutput
from langley_synthesis.service import orchestrate


def _risk(verdict: Verdict, confidence: float) -> TokenRiskReport:
    return TokenRiskReport(
        token_address="MINT",
        token_symbol="RG",
        verdict=verdict,
        confidence=confidence,
        summary="risk summary",
        signals=[
            RiskSignal(
                category=SignalCategory.LIQUIDITY,
                level=RiskLevel.CRITICAL,
                title="t",
                detail="d",
                evidence=[Evidence(field="liquidity_usd", observed_value="10")],
            )
        ]
        if verdict != Verdict.ABSTAIN
        else [],
        abstain_reason="r" if verdict == Verdict.ABSTAIN else None,
        data_provider="dexscreener+helius",
    )


def _forensics() -> ForensicsReport:
    return ForensicsReport(
        token_address="MINT-STAMPED",
        token_symbol="FX",
        profile_summary="neutral profile",
        findings=[
            Finding(
                dimension=ForensicDimension.HOLDERS,
                observation="concentrated",
                evidence=[Evidence(field="top10_holder_pct", observed_value="95")],
            )
        ],
        data_provider="dexscreener+helius",
    )


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    risk: TokenRiskReport | Exception,
    forensics: ForensicsReport | Exception,
    synthesis: SynthesisOutput,
) -> None:
    async def fake_risk(_q: str, **_k: Any) -> TokenRiskReport:
        if isinstance(risk, Exception):
            raise risk
        return risk

    async def fake_forensics(_q: str, **_k: Any) -> ForensicsReport:
        if isinstance(forensics, Exception):
            raise forensics
        return forensics

    class _FakeResult:
        def final_output_as(self, _t: type[Any]) -> SynthesisOutput:
            return synthesis

    async def fake_run(_agent: Any, **_k: Any) -> _FakeResult:
        return _FakeResult()

    monkeypatch.setattr(orchestrate, "analyze_token", fake_risk)
    monkeypatch.setattr(orchestrate, "analyze_onchain", fake_forensics)
    monkeypatch.setattr("langley_synthesis.service.orchestrate.Runner.run", fake_run)


_SYNTH = SynthesisOutput(
    headline="h", briefing="b", agreement=AgentAgreement.CORROBORATING, key_points=["a", "b"]
)


class TestOrchestrate:
    async def test_verdict_is_carried_verbatim_from_risk_guardian(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The synthesis output contains NO verdict; the report's verdict must come from RG.
        _patch(
            monkeypatch,
            risk=_risk(Verdict.LIKELY_UNSAFE, 0.9),
            forensics=_forensics(),
            synthesis=_SYNTH,
        )
        report = await orchestrate.synthesize_token("q")
        assert report.verdict == Verdict.LIKELY_UNSAFE
        assert report.confidence == 0.9
        assert report.contributing_agents == ["risk_guardian", "onchain_forensics"]
        # Identity mismatch (risk=MINT, forensics=MINT-STAMPED) -> trust the judged address.
        assert report.token_address == "MINT"
        # Non-safe verdict -> headline is anchored to the verdict stance even though the
        # synthesizer's raw headline was just "h".
        assert report.headline.startswith("Likely unsafe")

    async def test_degrades_when_forensics_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch(
            monkeypatch,
            risk=_risk(Verdict.LIKELY_SAFE, 0.8),
            forensics=RuntimeError("forensics down"),
            synthesis=_SYNTH,
        )
        report = await orchestrate.synthesize_token("q")
        assert report.verdict == Verdict.LIKELY_SAFE
        assert report.contributing_agents == ["risk_guardian"]
        assert report.forensic_findings == []
        assert report.headline == "h"  # safe verdict -> headline left as-is (no anchor)

    async def test_risk_guardian_failure_is_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from langley_risk.errors import AgentError

        _patch(
            monkeypatch,
            risk=RuntimeError("rg down"),
            forensics=_forensics(),
            synthesis=_SYNTH,
        )
        with pytest.raises(AgentError):
            await orchestrate.synthesize_token("q")
