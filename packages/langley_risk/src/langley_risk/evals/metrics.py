"""Eval metrics for the 'unsafe' verdict.

Positive class = **unsafe**. A confident wrong "safe" is the costly error, so we track
precision/recall/F1 on unsafe, plus abstain rate, evidence integrity, and calibration
(Brier score + Expected Calibration Error). Hand-rolled to avoid a scikit-learn dep.
"""

from __future__ import annotations

from dataclasses import dataclass

from langley_risk.domain.enums import Verdict
from langley_risk.domain.report import TokenRiskReport


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    """The scored result of one golden case."""

    case_id: str
    label_unsafe: bool
    predicted_unsafe: bool
    abstained: bool
    p_unsafe: float
    evidence_ok: bool


@dataclass(frozen=True, slots=True)
class Metrics:
    """Aggregate metrics over a set of cases."""

    n: int
    precision: float
    recall: float
    f1: float
    abstain_rate: float
    brier: float
    ece: float
    evidence_integrity: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int


def probability_unsafe(report: TokenRiskReport) -> float:
    """Map a report to P(token is unsafe) for calibration scoring."""
    if report.verdict == Verdict.LIKELY_UNSAFE:
        return report.confidence
    if report.verdict == Verdict.LIKELY_SAFE:
        return 1.0 - report.confidence
    return 0.5  # caution / abstain: maximally uncertain


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def compute_metrics(outcomes: list[CaseOutcome], *, n_bins: int = 10) -> Metrics:
    """Aggregate per-case outcomes into summary metrics."""
    n = len(outcomes)
    tp = sum(1 for o in outcomes if o.predicted_unsafe and o.label_unsafe)
    fp = sum(1 for o in outcomes if o.predicted_unsafe and not o.label_unsafe)
    fn = sum(1 for o in outcomes if not o.predicted_unsafe and o.label_unsafe)
    tn = sum(1 for o in outcomes if not o.predicted_unsafe and not o.label_unsafe)

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    abstain_rate = _safe_div(sum(1 for o in outcomes if o.abstained), n)
    evidence_integrity = _safe_div(sum(1 for o in outcomes if o.evidence_ok), n)
    brier = _safe_div(
        sum((o.p_unsafe - (1.0 if o.label_unsafe else 0.0)) ** 2 for o in outcomes), n
    )
    ece = _expected_calibration_error(outcomes, n_bins=n_bins)

    return Metrics(
        n=n,
        precision=precision,
        recall=recall,
        f1=f1,
        abstain_rate=abstain_rate,
        brier=brier,
        ece=ece,
        evidence_integrity=evidence_integrity,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
    )


def _expected_calibration_error(outcomes: list[CaseOutcome], *, n_bins: int) -> float:
    """Bin by predicted P(unsafe); weight |confidence - accuracy| by bin size."""
    if not outcomes:
        return 0.0
    bins: list[list[CaseOutcome]] = [[] for _ in range(n_bins)]
    for o in outcomes:
        idx = min(n_bins - 1, int(o.p_unsafe * n_bins))
        bins[idx].append(o)

    total = len(outcomes)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        avg_conf = sum(o.p_unsafe for o in bucket) / len(bucket)
        accuracy = sum(1 for o in bucket if o.label_unsafe) / len(bucket)
        ece += (len(bucket) / total) * abs(avg_conf - accuracy)
    return ece
