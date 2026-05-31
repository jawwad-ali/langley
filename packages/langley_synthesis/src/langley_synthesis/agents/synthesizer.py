"""Synthesis agent definition (no tools — it works on provided specialist reports)."""

from __future__ import annotations

from agents import Agent, ModelSettings

from langley_risk.config import Settings
from langley_synthesis.agents.prompts import SYNTHESIS_INSTRUCTIONS
from langley_synthesis.domain.report import SynthesisOutput


def build_synthesizer(settings: Settings) -> Agent[None]:
    """Construct the synthesis agent. It has no tools; its input is the two reports."""
    return Agent[None](
        name="Synthesis",
        instructions=SYNTHESIS_INSTRUCTIONS,
        model=settings.model,
        model_settings=ModelSettings(temperature=settings.temperature),
        output_type=SynthesisOutput,
    )
