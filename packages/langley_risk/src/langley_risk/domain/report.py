"""``TokenRiskReport`` and its parts — the agent's structured *output* contract.

This is what ``output_type`` binds the agent to. The validators here are
defense-in-depth layer **B** (structural): they make "every conclusive verdict is
backed by evidence" and "every abstain has a reason" hard invariants that malformed
LLM output cannot violate. Layer A is the prompt; layer C is the deterministic
post-process gate in ``service/postprocess.py``.

The schema is kept OpenAI strict-mode friendly: closed enums, explicit fields,
lists (never open-ended maps).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from langley_risk.domain.enums import CONCLUSIVE_VERDICTS, RiskLevel, SignalCategory, Verdict


class Evidence(BaseModel):
    """A single grounded data point backing a risk signal.

    ``field`` must name a field of the ``MarketSnapshot`` the agent was given, and
    ``observed_value`` is the stringified value the agent read from it. The
    post-process gate verifies the cited field actually exists and was non-null.
    """

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Name of the MarketSnapshot field this is drawn from.")
    observed_value: str = Field(description="The value observed in that field, as text.")


class RiskSignal(BaseModel):
    """One observation about the token, in a single risk dimension."""

    model_config = ConfigDict(extra="forbid")

    category: SignalCategory
    level: RiskLevel
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=600)
    evidence: list[Evidence] = Field(
        description="Concrete data points supporting this signal. Must be non-empty."
    )


def _no_signals() -> list[RiskSignal]:
    """Typed default factory for an empty signals list (keeps Pyright strict happy)."""
    return []


class TokenRiskReport(BaseModel):
    """The Risk Guardian's full, structured assessment of one token."""

    model_config = ConfigDict(extra="forbid")

    token_address: str
    token_symbol: str | None = None
    verdict: Verdict
    confidence: float = Field(
        ge=0.0, le=1.0, description="Calibrated probability the verdict is correct."
    )
    summary: str = Field(min_length=1, max_length=800)
    signals: list[RiskSignal] = Field(default_factory=_no_signals)
    abstain_reason: str | None = Field(
        default=None, description="Required when verdict is ABSTAIN; otherwise null."
    )
    data_provider: str = Field(description="Provider that supplied the underlying data.")

    @model_validator(mode="after")
    def _check_verdict_invariants(self) -> TokenRiskReport:
        """Enforce the evidence/abstain invariants (defense-in-depth layer B)."""
        if self.verdict == Verdict.ABSTAIN:
            if not (self.abstain_reason and self.abstain_reason.strip()):
                raise ValueError("ABSTAIN verdict requires a non-empty abstain_reason")
            return self

        # Conclusive verdicts must be backed by at least one evidenced signal.
        if self.verdict in CONCLUSIVE_VERDICTS:
            if not self.signals:
                raise ValueError(f"{self.verdict} verdict requires at least one risk signal")
            for signal in self.signals:
                if not signal.evidence:
                    raise ValueError(
                        f"Signal {signal.title!r} has no evidence; "
                        "every conclusive signal must cite data"
                    )
        return self
