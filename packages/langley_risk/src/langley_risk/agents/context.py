"""Run-scoped dependencies injected into the agent via ``RunContextWrapper``.

The OpenAI Agents SDK passes this object to tools as ``ctx.context``. Tools read the
``provider`` from here, which is the dependency-injection seam that keeps tools (and
the agent) decoupled from any concrete data source. It is never serialized or sent to
the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from langley_risk.config import Settings
from langley_risk.providers.base import DataProvider


@dataclass(slots=True)
class RiskDeps:
    """Dependencies available to Risk Guardian tools during a single run."""

    provider: DataProvider
    settings: Settings
    run_id: str
