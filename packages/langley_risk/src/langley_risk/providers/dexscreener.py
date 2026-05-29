"""Live DexScreener data provider.

Maps the free DexScreener API into our domain ``MarketSnapshot``. Transient
failures (timeouts, connection errors, 5xx) are retried with exponential backoff;
terminal failures are mapped onto the ``ProviderError`` hierarchy so the agent can
abstain appropriately.

Note: DexScreener provides market/liquidity/age data but NOT holder distribution or
mint/freeze-authority status. Those snapshot fields stay ``None`` here, which forces
the agent to abstain on the contract/holder dimensions rather than guess.
"""

from __future__ import annotations

import logging
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import (
    ProviderRateLimitedError,
    ProviderResponseInvalidError,
    ProviderTimeoutError,
    TokenNotFoundError,
)
from langley_risk.providers.base import ProviderName
from langley_risk.providers.models_raw import RawPair, RawPairsResponse

logger = logging.getLogger(__name__)

_MS_PER_HOUR = 1000 * 60 * 60
_MIN_MINT_LENGTH = 32

# HTTP status codes we branch on (named to avoid magic numbers).
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_FLOOR = 500


def _looks_like_mint(query: str) -> bool:
    """Heuristic: Solana mint addresses are long base58 strings with no spaces."""
    return len(query) >= _MIN_MINT_LENGTH and query.isalnum()


def _to_float(value: str | None) -> float | None:
    """DexScreener returns ``priceUsd`` as a string; parse leniently."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def map_pair_to_snapshot(pair: RawPair, query: str, now_ms: int) -> MarketSnapshot:
    """Map a raw DexScreener pair into a provider-neutral ``MarketSnapshot``."""
    age_hours: float | None = None
    if pair.pair_created_at is not None:
        age_hours = max(0.0, (now_ms - pair.pair_created_at) / _MS_PER_HOUR)

    txns_h24 = pair.txns.h24 if pair.txns else None
    return MarketSnapshot(
        query=query,
        chain=pair.chain_id,
        token_address=pair.base_token.address,
        token_symbol=pair.base_token.symbol,
        token_name=pair.base_token.name,
        pair_address=pair.pair_address,
        dex_id=pair.dex_id,
        url=pair.url,
        price_usd=_to_float(pair.price_usd),
        liquidity_usd=pair.liquidity.usd if pair.liquidity else None,
        fdv_usd=pair.fdv,
        market_cap_usd=pair.market_cap,
        volume_24h_usd=pair.volume.h24 if pair.volume else None,
        price_change_24h_pct=pair.price_change.h24 if pair.price_change else None,
        buys_24h=txns_h24.buys if txns_h24 else None,
        sells_24h=txns_h24.sells if txns_h24 else None,
        pair_created_at_ms=pair.pair_created_at,
        age_hours=age_hours,
        source_provider=ProviderName.DEXSCREENER.value,
    )


def _select_best_pair(pairs: list[RawPair]) -> RawPair:
    """Pick the most relevant pair — the one with the deepest USD liquidity."""
    return max(pairs, key=lambda p: (p.liquidity.usd if p.liquidity else 0.0) or 0.0)


class DexScreenerProvider:
    """Async DexScreener client implementing the ``DataProvider`` protocol."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Accept": "application/json"},
        )

    @property
    def name(self) -> str:
        return ProviderName.DEXSCREENER.value

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        response = await self._fetch_pairs(query)
        if not response.pairs:
            raise TokenNotFoundError(query)
        best = _select_best_pair(response.pairs)
        return map_pair_to_snapshot(best, query=query, now_ms=int(time.time() * 1000))

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def _request(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        return await self._client.get(path, params=params)

    async def _fetch_pairs(self, query: str) -> RawPairsResponse:
        if _looks_like_mint(query):
            path, params = f"/latest/dex/tokens/{query}", None
        else:
            path, params = "/latest/dex/search", {"q": query}

        try:
            resp = await self._request(path, params)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(self.name) from exc
        except httpx.TransportError as exc:
            raise ProviderResponseInvalidError(self.name, f"transport error: {exc}") from exc

        if resp.status_code == HTTP_TOO_MANY_REQUESTS:
            raise ProviderRateLimitedError(self.name)
        if resp.status_code == HTTP_NOT_FOUND:
            raise TokenNotFoundError(query)
        if resp.status_code >= HTTP_SERVER_ERROR_FLOOR:
            raise ProviderResponseInvalidError(self.name, f"server error {resp.status_code}")

        try:
            return RawPairsResponse.model_validate_json(resp.content)
        except ValueError as exc:
            raise ProviderResponseInvalidError(self.name, f"unparseable payload: {exc}") from exc
