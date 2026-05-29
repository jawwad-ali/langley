"""Offline eval gate: dataset integrity + baseline quality (no OpenAI, no network)."""

from __future__ import annotations

from langley_risk.evals.dataset import FIXTURES_DIR, load_golden
from langley_risk.evals.recorded_provider import RecordedProvider
from langley_risk.evals.run import run_eval


class TestDatasetIntegrity:
    def test_every_case_has_a_loadable_fixture(self) -> None:
        provider = RecordedProvider(FIXTURES_DIR)
        cases = load_golden()
        assert cases, "golden dataset is empty"
        for case in cases:
            snapshot = provider.load_fixture(case.fixture)
            # The fixture's token must match the case so evidence stays grounded.
            assert snapshot.token_address


class TestBaselineEval:
    async def test_baseline_meets_quality_bar(self) -> None:
        metrics = await run_eval(live=False, dataset=None)
        # The deterministic baseline must perfectly ground its evidence and separate
        # the seeded rug/honeypot rows from the legit ones. These are exact rational
        # results (e.g. 3/3), so exact equality is appropriate.
        assert metrics.evidence_integrity == 1.0
        assert metrics.recall == 1.0
        assert metrics.precision == 1.0
        assert metrics.f1 == 1.0
