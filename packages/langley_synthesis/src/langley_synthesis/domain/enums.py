"""Closed enumerations for the synthesis output (strict-mode friendly)."""

from __future__ import annotations

from enum import StrEnum


class AgentAgreement(StrEnum):
    """How much the on-chain profile CORROBORATES the (authoritative) verdict.

    Note there is deliberately no "contradicts" value: the Risk Guardian's verdict is
    authoritative, so the forensic profile can corroborate it strongly, partially, or not
    enough to say — but it never "overrides" or "diverges from" it.
    """

    CORROBORATING = "corroborating"  # forensic facts point the same way as the verdict
    TENSION = "tension"  # partial corroboration; some facts pull the other way (verdict stands)
    INSUFFICIENT = "insufficient"  # not enough forensic data to corroborate either way
