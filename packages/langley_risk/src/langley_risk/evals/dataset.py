"""Golden dataset schema and loader.

The golden set is the source of truth for "is the Risk Guardian any good?". Labels must
be *defensible* — each row records its rationale and provenance. v1 rows are seeded
with ``source="TODO-verify"`` and must be reviewed against on-chain history before any
quality claim is made.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DATASET = PACKAGE_ROOT / "evals" / "datasets" / "golden_v1.jsonl"
FIXTURES_DIR = PACKAGE_ROOT / "evals" / "fixtures" / "dexscreener"


class GoldenLabel(StrEnum):
    UNSAFE = "unsafe"
    SAFE = "safe"


class GoldenCase(BaseModel):
    """One labeled token in the golden dataset."""

    model_config = ConfigDict(extra="forbid")

    id: str
    query: str
    input_type: str = Field(description="'mint' or 'symbol'.")
    label: GoldenLabel
    label_subtype: str = Field(description="rug | honeypot | scam | legit | bluechip")
    rationale: str
    fixture: str = Field(description="Snapshot fixture filename under evals/fixtures/dexscreener.")
    source: str
    added: str
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


def load_golden(path: Path = GOLDEN_DATASET) -> list[GoldenCase]:
    """Load and validate the golden dataset (one JSON object per line)."""
    cases: list[GoldenCase] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        try:
            cases.append(GoldenCase.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"{path.name}:{line_no}: invalid golden case: {exc}") from exc
    return cases
