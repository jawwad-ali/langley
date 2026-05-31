"""Deterministic evidence-integrity gate for the forensic profile (no LLM).

Forensics issues no verdict, so the gate is simpler than the Risk Guardian's: it just
drops any finding that cites a field not actually present (non-null) in the snapshot the
agent saw. This keeps the profile grounded — every surviving observation is backed by
real data. (The Risk Guardian's danger/coverage/calibration rules don't apply here.)
"""

from __future__ import annotations

import logging

from langley_onchain.domain.report import Finding, ForensicsReport
from langley_risk.domain.market import MarketSnapshot

logger = logging.getLogger(__name__)


def _is_grounded(finding: Finding, citable: set[str]) -> bool:
    return bool(finding.evidence) and all(ev.field in citable for ev in finding.evidence)


def apply_integrity(report: ForensicsReport, snapshot: MarketSnapshot) -> ForensicsReport:
    """Drop findings whose cited fields are not present in the snapshot."""
    citable = snapshot.citable_fields()
    grounded = [f for f in report.findings if _is_grounded(f, citable)]
    if len(grounded) == len(report.findings):
        return report
    dropped = len(report.findings) - len(grounded)
    logger.info(
        "Forensics gate dropped %d ungrounded finding(s) for %s", dropped, report.token_address
    )
    update: dict[str, object] = {"findings": grounded}
    # If nothing grounded survives, the summary can no longer be trusted to describe real
    # data — replace it rather than leave it referencing dropped findings.
    if not grounded:
        update["profile_summary"] = (
            "Insufficient grounded on-chain data to produce a factual profile."
        )
    return report.model_copy(update=update)
