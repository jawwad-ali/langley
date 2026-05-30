"""Blind eval: run the live agent on the held-out outcome-verified test set.

Each token in golden_v3/test.jsonl is labeled by what ACTUALLY happened to it (died vs
survived). This runs the live agent (composite provider) on each and scores its verdict
against that real outcome — the first measurement on tokens the agent never influenced.

Honest caveat: the agent reads the token's CURRENT state, and the outcome label was
derived from that same current state (old + dead = died). So this tests whether the
agent's risk judgment aligns with real outcomes on real tokens — not a future-looking
prediction (that's shadow mode). The headline guard is still the fatal-error count.

Run: uv run python -m langley_risk.evals.run_v3
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from langley_risk.config import get_settings, load_env_file
from langley_risk.domain.enums import Verdict
from langley_risk.errors import LangleyRiskError
from langley_risk.evals.metrics import CaseOutcome, Metrics, compute_metrics, probability_unsafe
from langley_risk.observability.tracing import disable_tracing
from langley_risk.service.analyze import analyze_token

V3_DIR = Path(__file__).resolve().parents[3] / "evals" / "golden_v3"
TEST_SET = V3_DIR / "test.jsonl"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


async def _score_row(row: dict[str, Any]) -> tuple[CaseOutcome, str]:
    try:
        report = await analyze_token(row["query"], settings=get_settings())
        verdict = report.verdict
    except LangleyRiskError:
        verdict = Verdict.ABSTAIN
        report = None
    outcome = CaseOutcome(
        case_id=row["id"],
        label_unsafe=row["label"] == "unsafe",
        predicted_unsafe=verdict == Verdict.LIKELY_UNSAFE,
        abstained=verdict == Verdict.ABSTAIN,
        p_unsafe=probability_unsafe(report) if report else 0.5,
        evidence_ok=True,  # the gate enforces grounding; not separately measured here
    )
    return outcome, verdict.value


def _format(metrics: Metrics, table: list[tuple[str, str, str]], provider: str) -> str:
    fatal = [t for t in table if t[1] == "unsafe" and t[2] == Verdict.LIKELY_SAFE.value]
    false_pos = [t for t in table if t[1] == "safe" and t[2] == Verdict.LIKELY_UNSAFE.value]
    lines = [
        f"=== Held-out test (golden_v3, provider={provider}) - {metrics.n} tokens ===",
        "",
        f"FATAL (died token called LIKELY_SAFE): {len(fatal)}   <- must be 0",
        f"False positives (survived called UNSAFE): {len(false_pos)}",
        "",
        f"Precision (unsafe): {metrics.precision:.3f}",
        f"Recall    (unsafe): {metrics.recall:.3f}",
        f"F1        (unsafe): {metrics.f1:.3f}",
        f"Abstain rate:       {metrics.abstain_rate:.3f}",
        f"Confusion: TP={metrics.true_positives} FP={metrics.false_positives} "
        f"FN={metrics.false_negatives} TN={metrics.true_negatives}",
        "",
        "Per token (label -> verdict):",
    ]
    lines += [f"  {tid:<14} {label:<8} -> {verdict}" for tid, label, verdict in table]
    return "\n".join(lines)


async def run() -> tuple[Metrics, list[tuple[str, str, str]]]:
    disable_tracing()
    rows = _load_rows(TEST_SET)
    outcomes: list[CaseOutcome] = []
    table: list[tuple[str, str, str]] = []
    for row in rows:
        outcome, verdict = await _score_row(row)
        outcomes.append(outcome)
        table.append((row["id"], row["label"], verdict))
    return compute_metrics(outcomes), table


def main() -> int:
    load_env_file()
    metrics, table = asyncio.run(run())
    print(_format(metrics, table, get_settings().provider.value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
