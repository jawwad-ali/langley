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


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


class Detail:
    """Per-token result row for reporting (kept lightweight, not a dataclass field set)."""

    def __init__(self, tid: str, label: str, verdict: str, summary: str, cites: list[str]) -> None:
        self.tid = tid
        self.label = label
        self.verdict = verdict
        self.summary = summary
        self.cites = cites


async def _score_row(row: dict[str, Any]) -> tuple[CaseOutcome, Detail]:
    summary = ""
    cites: list[str] = []
    try:
        report = await analyze_token(row["query"], settings=get_settings())
        verdict = report.verdict
        summary = report.summary
        cites = sorted({ev.field for s in report.signals for ev in s.evidence})
    except LangleyRiskError as exc:
        verdict = Verdict.ABSTAIN
        report = None
        summary = f"error: {exc}"
    outcome = CaseOutcome(
        case_id=row["id"],
        label_unsafe=row["label"] == "unsafe",
        predicted_unsafe=verdict == Verdict.LIKELY_UNSAFE,
        abstained=verdict == Verdict.ABSTAIN,
        p_unsafe=probability_unsafe(report) if report else 0.5,
        evidence_ok=True,  # the gate enforces grounding; not separately measured here
    )
    return outcome, Detail(row["id"], row["label"], verdict.value, summary, cites)


def _is_misprediction(d: Detail) -> bool:
    if d.label == "unsafe":
        return d.verdict != Verdict.LIKELY_UNSAFE.value
    return d.verdict == Verdict.LIKELY_UNSAFE.value


def _format(metrics: Metrics, details: list[Detail], dataset: str, provider: str) -> str:
    safe_v = Verdict.LIKELY_SAFE.value
    unsafe_v = Verdict.LIKELY_UNSAFE.value
    fatal = [d for d in details if d.label == "unsafe" and d.verdict == safe_v]
    false_pos = [d for d in details if d.label == "safe" and d.verdict == unsafe_v]
    lines = [
        f"=== golden_v3/{dataset} (provider={provider}) - {metrics.n} tokens ===",
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
    lines += [
        f"  {'x' if _is_misprediction(d) else ' '} {d.tid:<14} {d.label:<8} -> {d.verdict}"
        for d in details
    ]
    mispred = [d for d in details if _is_misprediction(d)]
    if mispred:
        lines += ["", "Mispredictions (why):"]
        for d in mispred:
            lines.append(f"  {d.tid} [{d.verdict}] cites={d.cites}")
            lines.append(f"      {d.summary[:150]}")
    return "\n".join(lines)


async def run(dataset: str) -> tuple[Metrics, list[Detail]]:
    disable_tracing()
    rows = _load_rows(V3_DIR / dataset)
    outcomes: list[CaseOutcome] = []
    details: list[Detail] = []
    for row in rows:
        outcome, detail = await _score_row(row)
        outcomes.append(outcome)
        details.append(detail)
    return compute_metrics(outcomes), details


def main(argv: list[str] | None = None) -> int:
    import sys

    args = sys.argv[1:] if argv is None else argv
    dataset = args[0] if args else "test.jsonl"
    load_env_file()
    metrics, details = asyncio.run(run(dataset))
    print(_format(metrics, details, dataset, get_settings().provider.value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
