"""Risk Guardian agent definition.

``build_risk_guardian`` wires the model, tools, and structured output together. It is
a factory (not a module-level singleton) so the model/temperature can be configured
per environment and so tests can build isolated instances.
"""

from __future__ import annotations

from agents import Agent, ModelSettings

from langley_risk.agents.context import RiskDeps
from langley_risk.agents.prompts import RISK_GUARDIAN_INSTRUCTIONS
from langley_risk.config import Settings
from langley_risk.domain.report import TokenRiskReport
from langley_risk.tools.market_tools import get_token_market_data


def build_risk_guardian(settings: Settings) -> Agent[RiskDeps]:
    """Construct the Risk Guardian agent from settings."""
    return Agent[RiskDeps](
        name="Risk Guardian",
        instructions=RISK_GUARDIAN_INSTRUCTIONS,
        model=settings.model,
        model_settings=ModelSettings(temperature=settings.temperature),
        tools=[get_token_market_data],
        output_type=TokenRiskReport,
    )
