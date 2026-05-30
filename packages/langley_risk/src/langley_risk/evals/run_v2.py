"""Visibility-aware eval over the real golden_v2 dataset.

Unlike the v1 harness (single precision/recall number on synthetic data), this scores
real tokens and breaks results down by what the agent could *fairly* be expected to do:

- legit                       → should NOT flag unsafe (abstain is acceptable-cautious).
- unsafe / dexscreener_visible→ should CATCH (verdict unsafe).
- unsafe / contract_only      → should ABSTAIN (danger is invisible to DexScreener);
                                calling it "safe" is the fatal error, flagging unsafe is luck.
- synthetic controls          → sanity-check visible-danger detection.

The headline number is the **fatal-error count**: any token whose true label is unsafe
but the agent called LIKELY_SAFE. That must be 0.

Run: uv run python -m langley_risk.evals.run_v2
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from langley_risk.config import get_settings, load_env_file
from langley_risk.domain.enums import Verdict
from langley_risk.evals.recorded_provider import RecordedProvider
from langley_risk.observability.tracing import disable_tracing
from langley_risk.service.analyze import analyze_token

V2_DIR = Path(__file__).resolve().parents[3] / "evals" / "golden_v2"
DATASET_V2 = V2_DIR / "golden_v2.jsonl"
FIXTURES_V2 = V2_DIR / "fixtures"


@dataclass(frozen=True, slots=True)
class RowOutcome:
    id: str
    label: str
    danger_visibility: str
    source: str
    verdict: str


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


async def _score_row(row: dict[str, Any]) -> RowOutcome:
    provider = RecordedProvider(FIXTURES_V2)
    provider.load_fixture(row["fixture"])
    report = await analyze_token(row["query"], provider=provider, settings=get_settings())
    return RowOutcome(
        id=row["id"],
        label=row["label"],
        danger_visibility=row.get("danger_visibility", "na"),
        source=row.get("source", "real"),
        verdict=report.verdict.value,
    )


def _pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.0f}%" if d else "—"


def _bucket_report(title: str, rows: list[RowOutcome]) -> list[str]:
    if not rows:
        return [f"{title}: (none)"]
    n = len(rows)
    unsafe = sum(1 for r in rows if r.verdict == Verdict.LIKELY_UNSAFE.value)
    safe = sum(1 for r in rows if r.verdict == Verdict.LIKELY_SAFE.value)
    abstain = sum(1 for r in rows if r.verdict == Verdict.ABSTAIN.value)
    caution = sum(1 for r in rows if r.verdict == Verdict.CAUTION.value)
    return [
        f"{title}  (n={n})",
        f"    likely_unsafe={unsafe} ({_pct(unsafe, n)})  "
        f"likely_safe={safe} ({_pct(safe, n)})  "
        f"abstain={abstain} ({_pct(abstain, n)})  caution={caution}",
    ]


def format_report(outcomes: list[RowOutcome], provider: str) -> str:
    legit = [o for o in outcomes if o.label == "safe"]
    visible = [
        o for o in outcomes if o.label == "unsafe" and o.danger_visibility == "dexscreener_visible"
    ]
    contract = [
        o for o in outcomes if o.label == "unsafe" and o.danger_visibility == "contract_only"
    ]
    real = [o for o in outcomes if o.source == "real"]
    synthetic = [o for o in outcomes if o.source == "synthetic"]

    fatal = [o for o in outcomes if o.label == "unsafe" and o.verdict == Verdict.LIKELY_SAFE.value]
    false_pos = [o for o in legit if o.verdict == Verdict.LIKELY_UNSAFE.value]

    # With a contract-data provider the agent CAN see contract-only danger, so it should
    # now CATCH it; on the DexScreener-only path it can only safely ABSTAIN.
    enriched = provider not in ("dexscreener", "recorded")
    contract_expectation = (
        "expect CATCH (contract data available)" if enriched else "expect ABSTAIN"
    )

    lines = [
        f"=== Risk Guardian eval - golden_v2 (provider={provider}; {len(outcomes)} tokens: "
        f"{len(real)} real, {len(synthetic)} synthetic) ===",
        "",
        f"FATAL errors (true unsafe called LIKELY_SAFE): {len(fatal)}   <- must be 0",
        f"False positives (legit called LIKELY_UNSAFE):  {len(false_pos)}",
        "",
        "By bucket (what the agent SHOULD do):",
        *_bucket_report("  Legit -> expect likely_safe/abstain", legit),
        *_bucket_report("  Unsafe, DexScreener-visible -> expect CATCH (unsafe)", visible),
        *_bucket_report(f"  Unsafe, contract-only -> {contract_expectation}", contract),
    ]
    if fatal:
        lines += ["", "FATAL cases:"] + [f"    {o.id} ({o.danger_visibility})" for o in fatal]
    return "\n".join(lines)


async def run() -> list[RowOutcome]:
    disable_tracing()
    rows = _load_rows(DATASET_V2)
    return [await _score_row(r) for r in rows]


def main() -> int:
    load_env_file()
    outcomes = asyncio.run(run())
    report = format_report(outcomes, get_settings().provider.value)
    print(report)
    (V2_DIR / "eval_results.json").write_text(
        json.dumps([asdict(o) for o in outcomes], indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
