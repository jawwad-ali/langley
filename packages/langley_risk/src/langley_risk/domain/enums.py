"""Closed enumerations used across the domain models.

These are intentionally string enums with a small, closed set of members so the
agent's output JSON schema stays OpenAI *strict-mode* compatible (no open-ended
strings where a category is expected).
"""

from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
    """The Risk Guardian's top-level conclusion about a token.

    ``ABSTAIN`` is a first-class outcome: when evidence is insufficient the agent
    must abstain rather than guess. A confident wrong "safe" verdict is the only
    truly fatal error for this product.
    """

    LIKELY_SAFE = "likely_safe"
    CAUTION = "caution"
    LIKELY_UNSAFE = "likely_unsafe"
    ABSTAIN = "abstain"


class RiskLevel(StrEnum):
    """Severity of an individual risk signal."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalCategory(StrEnum):
    """The dimension a risk signal speaks to."""

    LIQUIDITY = "liquidity"
    HOLDER_DISTRIBUTION = "holder_distribution"
    CONTRACT = "contract"
    TRADING_ACTIVITY = "trading_activity"
    AGE = "age"
    METADATA = "metadata"


# Verdicts that assert a non-trivial conclusion and therefore require evidence.
# (Everything except ABSTAIN — an abstain requires a reason, not evidence.)
CONCLUSIVE_VERDICTS: frozenset[Verdict] = frozenset(
    {Verdict.LIKELY_SAFE, Verdict.CAUTION, Verdict.LIKELY_UNSAFE}
)
