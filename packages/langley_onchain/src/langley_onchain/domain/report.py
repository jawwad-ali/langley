"""``ForensicsReport`` — the On-Chain Forensics agent's output contract.

Deliberately NOT a safety verdict (that is the Risk Guardian's job). This is a neutral,
evidence-cited *profile*: per-dimension factual observations plus a one-line summary.
Every finding must cite a field from the data it was derived from — the same grounding
discipline as the Risk Guardian, enforced by the validator here and the integrity gate.

The ``Evidence`` model is reused from langley_risk so a citation means the same thing
across agents.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from langley_onchain.domain.enums import ForensicDimension
from langley_risk.domain.report import Evidence


def _no_findings() -> list[Finding]:
    """Typed default factory (keeps Pyright strict happy)."""
    return []


class Finding(BaseModel):
    """One neutral, evidence-cited observation about a single dimension."""

    model_config = ConfigDict(extra="forbid")

    dimension: ForensicDimension
    observation: str = Field(min_length=1, max_length=600)
    evidence: list[Evidence] = Field(
        description="Concrete data points this observation is drawn from. Must be non-empty."
    )


class ForensicsReport(BaseModel):
    """A neutral on-chain/market profile of one token."""

    model_config = ConfigDict(extra="forbid")

    token_address: str
    token_symbol: str | None = None
    profile_summary: str = Field(min_length=1, max_length=800)
    findings: list[Finding] = Field(default_factory=_no_findings)
    data_provider: str

    @model_validator(mode="after")
    def _every_finding_is_evidenced(self) -> ForensicsReport:
        for finding in self.findings:
            if not finding.evidence:
                raise ValueError(
                    f"Finding on {finding.dimension} has no evidence; "
                    "every forensic observation must cite data"
                )
        return self
