"""Unit tests for the Helius contract enricher (RPC parsing + error mapping)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from langley_risk.domain.contract import ContractInfo
from langley_risk.errors import ProviderResponseInvalidError, TokenNotFoundError
from langley_risk.providers.helius import HeliusEnricher, parse_contract_info

RPC = "https://mainnet.helius-rpc.com"
MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


def _account(
    mint_authority: str | None, freeze_authority: str | None, supply: str
) -> dict[str, Any]:
    """The `value` payload of a getAccountInfo result for an SPL mint."""
    return {
        "data": {
            "parsed": {
                "type": "mint",
                "info": {
                    "mintAuthority": mint_authority,
                    "freezeAuthority": freeze_authority,
                    "supply": supply,
                    "decimals": 0,
                },
            }
        }
    }


class TestParseContractInfo:
    def test_renounced_authorities_and_concentration(self) -> None:
        largest: list[dict[str, Any]] = [
            {"uiAmount": 500.0},
            {"uiAmount": 300.0},
            {"uiAmount": 50.0},
        ]
        info = parse_contract_info(_account(None, None, "1000"), largest)
        assert info.mint_authority_renounced is True
        assert info.freeze_authority_renounced is True
        pct = info.top10_holder_pct
        assert pct is not None and round(pct, 6) == 85.0  # 850 / 1000

    def test_enabled_mint_authority_is_not_renounced(self) -> None:
        account = _account("SomeAuthorityPubkey1111111111111111111111111", None, "1000")
        info = parse_contract_info(account, [])
        assert info.mint_authority_renounced is False

    def test_unparseable_account_raises(self) -> None:
        with pytest.raises(ProviderResponseInvalidError):
            parse_contract_info({"data": {}}, [])

    def test_non_mint_account_raises(self) -> None:
        # A token *account* (type="account") must not be mis-parsed as a mint.
        token_account: dict[str, Any] = {
            "data": {"parsed": {"type": "account", "info": {"owner": "x"}}}
        }
        with pytest.raises(ProviderResponseInvalidError):
            parse_contract_info(token_account, [])

    def test_empty_holder_list_yields_unknown_not_zero(self) -> None:
        # A partial RPC (no largest accounts) must NOT manufacture a fake "0% concentrated".
        info = parse_contract_info(_account(None, None, "1000"), [])
        assert info.top10_holder_pct is None


async def _fetch() -> ContractInfo:
    enricher = HeliusEnricher(api_key="k", rpc_url=RPC, timeout_seconds=10.0)
    try:
        return await enricher.get_contract_info(MINT)
    finally:
        await enricher.aclose()


def _rpc(result: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "result": result})


class TestHeliusEnricher:
    async def test_maps_separate_calls_into_contract_info(self) -> None:
        # Two sequential calls: getAccountInfo, then getTokenLargestAccounts.
        account = _rpc({"value": _account(None, None, "1000")})
        largest = _rpc({"value": [{"uiAmount": 950.0}]})
        async with respx.mock(base_url=RPC) as mock:
            mock.post("/").mock(side_effect=[account, largest])
            info = await _fetch()
        assert info.mint_authority_renounced is True
        pct = info.top10_holder_pct
        assert pct is not None and round(pct, 6) == 95.0
        assert info.source_provider == "helius"

    async def test_missing_account_raises_not_found(self) -> None:
        async with respx.mock(base_url=RPC) as mock:
            mock.post("/").mock(return_value=_rpc({"value": None}))
            with pytest.raises(TokenNotFoundError):
                await _fetch()

    async def test_largest_failure_still_returns_authority(self) -> None:
        # If getTokenLargestAccounts fails (e.g. free-tier overload), authority data is
        # still returned with concentration left unknown — not discarded.
        account = _rpc({"value": _account(None, None, "1000")})
        error = httpx.Response(200, json={"id": "1", "error": {"code": -32603, "message": "busy"}})
        async with respx.mock(base_url=RPC) as mock:
            mock.post("/").mock(side_effect=[account, error])
            info = await _fetch()
        assert info.mint_authority_renounced is True
        assert info.top10_holder_pct is None

    async def test_rpc_error_raises_response_invalid(self) -> None:
        error_body = {
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32403, "message": "paid only"},
        }
        async with respx.mock(base_url=RPC) as mock:
            mock.post("/").mock(return_value=httpx.Response(200, json=error_body))
            with pytest.raises(ProviderResponseInvalidError):
                await _fetch()
