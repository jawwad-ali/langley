"""Request models for the demo API. Responses reuse langley_risk's domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """A single token-analysis request."""

    query: str = Field(min_length=1, max_length=120, description="Solana mint address or symbol.")
