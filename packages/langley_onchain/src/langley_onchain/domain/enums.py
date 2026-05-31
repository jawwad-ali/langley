"""Closed enumerations for the forensic profile (strict-mode friendly)."""

from __future__ import annotations

from enum import StrEnum


class ForensicDimension(StrEnum):
    """The on-chain/market dimension a finding speaks to."""

    LIQUIDITY = "liquidity"
    HOLDERS = "holders"  # holder_count/top10 require a contract provider (Helius); else null
    AUTHORITIES = "authorities"  # mint/freeze authority require a contract provider (Helius)
    ACTIVITY = "activity"
    AGE = "age"
