"""On-Chain Forensics agent definition.

A factory (not a singleton) so model/temperature are configurable per environment and
tests can build isolated instances — same pattern as the Risk Guardian.
"""

from __future__ import annotations

from agents import Agent, ModelSettings

from langley_onchain.agents.context import ForensicsDeps
from langley_onchain.agents.prompts import FORENSICS_INSTRUCTIONS
from langley_onchain.domain.report import ForensicsReport
from langley_onchain.tools.onchain_tools import get_onchain_snapshot
from langley_risk.config import Settings


def build_forensics_agent(settings: Settings) -> Agent[ForensicsDeps]:
    """Construct the On-Chain Forensics agent from settings."""
    return Agent[ForensicsDeps](
        name="On-Chain Forensics",
        instructions=FORENSICS_INSTRUCTIONS,
        model=settings.model,
        model_settings=ModelSettings(temperature=settings.temperature),
        tools=[get_onchain_snapshot],
        output_type=ForensicsReport,
    )
