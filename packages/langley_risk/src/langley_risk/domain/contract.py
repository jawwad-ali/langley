"""``ContractInfo`` — contract-level facts an enricher adds to a ``MarketSnapshot``.

These are the fields DexScreener cannot see (mint/freeze authority, holder
concentration, LP lock). A ``ContractEnricher`` (e.g. Helius) produces this; the
``CompositeProvider`` merges the non-null fields into the snapshot. Field names match
``MarketSnapshot`` exactly so merging is a direct update.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# The MarketSnapshot fields this enrichment can populate.
CONTRACT_FIELDS = (
    "holder_count",
    "top10_holder_pct",
    "mint_authority_renounced",
    "freeze_authority_renounced",
    "lp_locked_or_burned",
)


class ContractInfo(BaseModel):
    """Contract-level signals for a single mint (all optional; null = unknown)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    holder_count: int | None = Field(default=None, ge=0)
    top10_holder_pct: float | None = Field(default=None, ge=0, le=100)
    mint_authority_renounced: bool | None = Field(
        default=None, description="True if no one can mint more (good); False if mintable."
    )
    freeze_authority_renounced: bool | None = Field(
        default=None, description="True if no one can freeze wallets (good)."
    )
    lp_locked_or_burned: bool | None = Field(default=None)
    source_provider: str = Field(description="Enricher that produced this info.")

    def contract_updates(self) -> dict[str, Any]:
        """Return the non-null contract fields, for merging into a MarketSnapshot."""
        return {
            field: value for field in CONTRACT_FIELDS if (value := getattr(self, field)) is not None
        }
