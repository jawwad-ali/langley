"""Raw DexScreener wire-format models.

These mirror the DexScreener JSON payload exactly (camelCase keys, ``priceUsd`` as a
string, etc.). They exist only so parsing is type-checked and isolated; the mapping
from these into the domain ``MarketSnapshot`` lives in ``dexscreener.py``. Unknown
keys are ignored so upstream additions don't break us.

Reference: https://docs.dexscreener.com/api/reference
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_RAW = ConfigDict(populate_by_name=True, extra="ignore")


class RawToken(BaseModel):
    model_config = _RAW

    address: str
    name: str | None = None
    symbol: str | None = None


class RawTxnWindow(BaseModel):
    model_config = _RAW

    buys: int | None = None
    sells: int | None = None


class RawTxns(BaseModel):
    model_config = _RAW

    h24: RawTxnWindow | None = None


class RawVolume(BaseModel):
    model_config = _RAW

    h24: float | None = None


class RawPriceChange(BaseModel):
    model_config = _RAW

    h24: float | None = None


class RawLiquidity(BaseModel):
    model_config = _RAW

    usd: float | None = None
    base: float | None = None
    quote: float | None = None


class RawPair(BaseModel):
    model_config = _RAW

    chain_id: str = Field(alias="chainId")
    dex_id: str | None = Field(default=None, alias="dexId")
    url: str | None = None
    pair_address: str | None = Field(default=None, alias="pairAddress")
    base_token: RawToken = Field(alias="baseToken")
    quote_token: RawToken | None = Field(default=None, alias="quoteToken")
    price_usd: str | None = Field(default=None, alias="priceUsd")
    txns: RawTxns | None = None
    volume: RawVolume | None = None
    price_change: RawPriceChange | None = Field(default=None, alias="priceChange")
    liquidity: RawLiquidity | None = None
    fdv: float | None = None
    market_cap: float | None = Field(default=None, alias="marketCap")
    pair_created_at: int | None = Field(default=None, alias="pairCreatedAt")


class RawPairsResponse(BaseModel):
    """Shape of both the /tokens and /search DexScreener endpoints."""

    model_config = _RAW

    schema_version: str | None = Field(default=None, alias="schemaVersion")
    pairs: list[RawPair] | None = None
