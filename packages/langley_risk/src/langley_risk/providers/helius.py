"""Helius contract enricher.

Reads contract-level facts a market source (DexScreener) cannot see, via standard
Solana JSON-RPC over the Helius endpoint:

- ``getAccountInfo`` (jsonParsed) on the mint -> mint/freeze authority + supply.
  A *null* authority means it has been renounced (safer); a present authority means
  someone can still mint/freeze.
- ``getTokenLargestAccounts`` -> top holders, from which we derive top-10 concentration.

Both are sent as one batched RPC request. Holder count and LP-lock status are not
derivable from these calls, so they remain null (unknown) for now.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from langley_risk.domain.contract import ContractInfo
from langley_risk.errors import (
    ProviderError,
    ProviderRateLimitedError,
    ProviderResponseInvalidError,
    ProviderTimeoutError,
    TokenNotFoundError,
)
from langley_risk.providers.base import ProviderName

logger = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429
_TOP_N = 10


def _as_dict(value: Any) -> dict[str, Any]:
    """Coerce an untrusted JSON value to a dict (empty if it isn't one)."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    """Coerce an untrusted JSON value to a list of dicts."""
    if not isinstance(value, list):
        return []
    items = cast("list[Any]", value)
    return [cast("dict[str, Any]", item) for item in items if isinstance(item, dict)]


def _largest_concentration_pct(largest: list[dict[str, Any]], ui_supply: float) -> float | None:
    """Top-10 holders' share of TOTAL supply, as a percent — or None if unknown.

    Only the top ~20 accounts are available, so the top-10 numerator is exact; the
    denominator is total on-chain supply (incl. burned + LP/pool tokens), so this is a
    conservative LOWER BOUND on float concentration. Returns None when no holder data is
    present so a partial/empty RPC result can never be mistaken for "0% concentrated"
    (which the agent would read as a positive safety signal — a false-safe path).
    """
    if ui_supply <= 0 or not largest:
        return None
    total_top = sum(
        sorted((float(e.get("uiAmount") or 0.0) for e in largest), reverse=True)[:_TOP_N]
    )
    if total_top <= 0:
        return None
    return min(100.0, total_top / ui_supply * 100.0)


def parse_contract_info(
    account_value: dict[str, Any], largest: list[dict[str, Any]]
) -> ContractInfo:
    """Build ContractInfo from getAccountInfo + getTokenLargestAccounts results."""
    parsed = _as_dict(_as_dict(account_value.get("data")).get("parsed"))
    # getAccountInfo(jsonParsed) returns the same {type, info} envelope for ANY spl-token
    # account; guard that this address is actually a MINT, else we'd silently mis-report a
    # token/other account as "authority unknown" instead of failing.
    if parsed.get("type") != "mint":
        raise ProviderResponseInvalidError(
            ProviderName.HELIUS.value, f"account is not an SPL mint (type={parsed.get('type')!r})"
        )
    info = _as_dict(parsed.get("info"))
    if not info:
        raise ProviderResponseInvalidError(
            ProviderName.HELIUS.value, "mint account has no parsed info"
        )

    mint_auth = info.get("mintAuthority", "missing")
    freeze_auth = info.get("freezeAuthority", "missing")
    mint_renounced = mint_auth is None if mint_auth != "missing" else None
    freeze_renounced = freeze_auth is None if freeze_auth != "missing" else None

    top10_pct: float | None = None
    try:
        ui_supply = int(info["supply"]) / (10 ** int(info["decimals"]))
        top10_pct = _largest_concentration_pct(largest, ui_supply)
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        top10_pct = None

    return ContractInfo(
        mint_authority_renounced=mint_renounced,
        freeze_authority_renounced=freeze_renounced,
        top10_holder_pct=top10_pct,
        source_provider=ProviderName.HELIUS.value,
    )


class HeliusEnricher:
    """Contract enricher backed by the Helius Solana RPC endpoint."""

    def __init__(self, api_key: str, rpc_url: str, timeout_seconds: float) -> None:
        # Helius authenticates via the api-key query param (its RPC endpoint has no header
        # auth). This module never logs the URL or uses exc_info, so the key is not emitted;
        # don't add such logging here, and prefer redaction in any observability hooks.
        self._url = f"{rpc_url.rstrip('/')}/?api-key={api_key}"
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds, headers={"Content-Type": "application/json"}
        )

    @property
    def name(self) -> str:
        return ProviderName.HELIUS.value

    async def get_contract_info(self, mint: str) -> ContractInfo:
        # Two separate RPC calls, NOT a JSON-RPC batch: Helius rejects batched requests
        # on the free plan ("Batch requests are only available for paid plans").
        account = await self._rpc_call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        account_value = account.get("value")
        if account_value is None:
            raise TokenNotFoundError(mint)
        # Holder concentration is BEST-EFFORT: getTokenLargestAccounts is heavy and is
        # transiently unavailable on the free tier. If it fails we still return the
        # (more important) authority data, leaving top10_holder_pct unknown rather than
        # discarding everything.
        largest: list[dict[str, Any]] = []
        try:
            largest_result = await self._rpc_call("getTokenLargestAccounts", [mint])
            largest = _as_dict_list(largest_result.get("value"))
        except ProviderError as exc:
            logger.warning("getTokenLargestAccounts unavailable for %s (continuing): %s", mint, exc)
        return parse_contract_info(_as_dict(account_value), largest)

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        return await self._client.post(self._url, json=body)

    async def _rpc_call(self, method: str, params: list[Any]) -> dict[str, Any]:
        body: dict[str, Any] = {"jsonrpc": "2.0", "id": "1", "method": method, "params": params}
        try:
            resp = await self._post(body)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(self.name) from exc
        except httpx.TransportError as exc:
            raise ProviderResponseInvalidError(self.name, f"transport error: {exc}") from exc

        if resp.status_code == HTTP_TOO_MANY_REQUESTS:
            raise ProviderRateLimitedError(self.name)
        if resp.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
            raise ProviderResponseInvalidError(self.name, f"server error {resp.status_code}")

        try:
            payload = _as_dict(resp.json())
        except ValueError as exc:
            raise ProviderResponseInvalidError(self.name, f"unparseable payload: {exc}") from exc

        if "error" in payload:
            raise ProviderResponseInvalidError(self.name, f"rpc error: {payload['error']}")
        return _as_dict(payload.get("result"))
