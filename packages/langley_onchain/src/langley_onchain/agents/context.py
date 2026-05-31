"""Run-scoped dependencies injected into the Forensics agent via ``RunContextWrapper``.

Mirrors the Risk Guardian's DI seam: tools read the provider from here, so nothing
imports a concrete data source. The provider is reused from langley_risk (DexScreener +
optional Helius enrichment), so the forensic profile sees the same market + contract data.
"""

from __future__ import annotations

from dataclasses import dataclass

from langley_risk.config import Settings
from langley_risk.providers.base import DataProvider


@dataclass(slots=True)
class ForensicsDeps:
    """Dependencies available to On-Chain Forensics tools during a single run."""

    provider: DataProvider
    settings: Settings
    run_id: str
