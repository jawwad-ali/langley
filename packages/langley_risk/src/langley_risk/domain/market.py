"""``MarketSnapshot`` — the provider-neutral market data the agent reasons over.

This is the *input* contract. Every data provider (DexScreener now; Helius/Birdeye
later) maps its raw payload into this shape, so the agent and the post-process gate
never depend on a specific provider's JSON.

Fields that a given provider cannot supply are ``None``. That is deliberate and
load-bearing: the agent must **abstain** on any dimension whose backing field is
``None`` rather than invent a value. The free DexScreener API, for example, cannot
report holder distribution or mint/freeze-authority status — so those fields stay
``None`` and the agent cannot legitimately claim a contract is "safe".
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketSnapshot(BaseModel):
    """A normalized, point-in-time view of a token's market data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- Identity ---
    query: str = Field(description="The original user query (mint address or symbol).")
    chain: str = Field(description="Chain id, e.g. 'solana'.")
    token_address: str = Field(description="The token mint address.")
    token_symbol: str | None = Field(default=None, description="Token ticker symbol.")
    token_name: str | None = Field(default=None, description="Token display name.")
    pair_address: str | None = Field(default=None, description="The DEX pair address used.")
    dex_id: str | None = Field(default=None, description="DEX identifier, e.g. 'raydium'.")
    url: str | None = Field(default=None, description="Provider URL for the pair.")

    # --- Market / liquidity (provider may supply a subset) ---
    price_usd: float | None = Field(default=None, ge=0)
    liquidity_usd: float | None = Field(default=None, ge=0)
    fdv_usd: float | None = Field(default=None, ge=0, description="Fully diluted valuation.")
    market_cap_usd: float | None = Field(default=None, ge=0)
    volume_24h_usd: float | None = Field(default=None, ge=0)
    price_change_24h_pct: float | None = Field(default=None)

    # --- Trading activity ---
    buys_24h: int | None = Field(default=None, ge=0)
    sells_24h: int | None = Field(default=None, ge=0)

    # --- Age ---
    pair_created_at_ms: int | None = Field(
        default=None, ge=0, description="Pair creation time, unix epoch milliseconds."
    )
    age_hours: float | None = Field(
        default=None, ge=0, description="Derived age of the pair in hours, if known."
    )

    # --- Contract / holders (NOT available from DexScreener; needs Helius/Birdeye) ---
    holder_count: int | None = Field(default=None, ge=0)
    top10_holder_pct: float | None = Field(default=None, ge=0, le=100)
    mint_authority_renounced: bool | None = Field(default=None)
    freeze_authority_renounced: bool | None = Field(default=None)
    lp_locked_or_burned: bool | None = Field(default=None)

    # --- Provenance ---
    source_provider: str = Field(description="Name of the provider that produced this snapshot.")

    def citable_fields(self) -> set[str]:
        """Return the set of field names that hold a non-null value.

        The post-process gate uses this to verify that every piece of evidence the
        agent cites actually corresponds to data the agent was given — a cited field
        that is ``None`` (or unknown) means the claim was not grounded in real data.
        """
        return {name for name, value in self.__dict__.items() if value is not None}
