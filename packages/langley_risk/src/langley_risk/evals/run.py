"""Eval harness entrypoint.

Default (``--stub``, the free CI/demo path) scores the deterministic baseline with zero
OpenAI spend. ``--live`` runs the real GPT-4o agent against recorded data (needs
``OPENAI_API_KEY``). Both apply the same deterministic gate, so the numbers are
comparable — the live agent should beat the baseline.

    python -m langley_risk.evals.run          # baseline (free)
    python -m langley_risk.evals.run --live   # real agent (needs OPENAI_API_KEY)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from langley_risk.config import get_settings
from langley_risk.domain.enums import Verdict
from langley_risk.domain.report import TokenRiskReport
from langley_risk.evals.baseline import baseline_report
from langley_risk.evals.dataset import FIXTURES_DIR, GoldenCase, GoldenLabel, load_golden
from langley_risk.evals.metrics import CaseOutcome, Metrics, compute_metrics, probability_unsafe
from langley_risk.evals.recorded_provider import RecordedProvider
from langley_risk.observability.tracing import disable_tracing
from langley_risk.service.analyze import analyze_token
from langley_risk.service.postprocess import apply_gate, evidence_is_grounded


async def _score_case(case: GoldenCase, *, live: bool) -> CaseOutcome:
    provider = RecordedProvider(FIXTURES_DIR)
    snapshot = provider.load_fixture(case.fixture)
    if live:
        report: TokenRiskReport = await analyze_token(
            case.query, provider=provider, settings=get_settings()
        )
    else:
        report = apply_gate(baseline_report(snapshot), snapshot)

    return CaseOutcome(
        case_id=case.id,
        label_unsafe=case.label == GoldenLabel.UNSAFE,
        predicted_unsafe=report.verdict == Verdict.LIKELY_UNSAFE,
        abstained=report.verdict == Verdict.ABSTAIN,
        p_unsafe=probability_unsafe(report),
        evidence_ok=evidence_is_grounded(report, snapshot),
    )


def _format_metrics(metrics: Metrics, *, mode: str) -> str:
    return "\n".join(
        [
            f"=== Risk Guardian eval ({mode}) - {metrics.n} cases ===",
            f"Precision (unsafe): {metrics.precision:.3f}",
            f"Recall    (unsafe): {metrics.recall:.3f}",
            f"F1        (unsafe): {metrics.f1:.3f}",
            f"Abstain rate:       {metrics.abstain_rate:.3f}",
            f"Evidence integrity: {metrics.evidence_integrity:.3f}",
            f"Brier score:        {metrics.brier:.3f}  (lower is better)",
            f"ECE:                {metrics.ece:.3f}  (lower is better)",
            f"Confusion: TP={metrics.true_positives} FP={metrics.false_positives} "
            f"FN={metrics.false_negatives} TN={metrics.true_negatives}",
        ]
    )


async def run_eval(*, live: bool, dataset: Path | None) -> Metrics:
    """Run the eval and return the aggregate metrics."""
    disable_tracing()
    cases = load_golden(dataset) if dataset else load_golden()
    outcomes = [await _score_case(c, live=live) for c in cases]
    return compute_metrics(outcomes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="langley-risk-eval", description="Run the eval harness.")
    parser.add_argument("--live", action="store_true", help="Use the real agent (needs OpenAI).")
    parser.add_argument("--dataset", type=Path, default=None, help="Override golden dataset path.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.live and not os.environ.get("OPENAI_API_KEY"):
        print("error: --live requires OPENAI_API_KEY", file=sys.stderr)
        return 2

    metrics = asyncio.run(run_eval(live=args.live, dataset=args.dataset))
    print(_format_metrics(metrics, mode="live agent" if args.live else "baseline"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
