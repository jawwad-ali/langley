"""Gather a real candidate-token pool with multi-source evidence for labeling.

Deterministic data collection (no LLM): for each candidate Solana mint it fetches a
compact "evidence pack" from three independent sources:

- DexScreener  — what the agent itself sees (liquidity, age, trading).
- RugCheck     — contract-level truth (risk score, LP lock %, mint/freeze authority).
- GoPlus       — token-security flags (mintable/freezable/closable/...).

Output is a JSON list written to evals/golden_v2/evidence.json, consumed by the
labeling+verification workflow. Labels are NOT assigned here — only evidence collected.

Run: uv run python packages/langley_risk/scripts/gather_candidates.py [--profiles N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

OUT_DIR = Path(__file__).resolve().parents[1] / "evals" / "golden_v2"
OUT_FILE = OUT_DIR / "evidence.json"

# Well-known, established Solana tokens — the high-confidence "legit" pool.
CURATED_LEGIT: dict[str, str] = {
    "So11111111111111111111111111111111111111112": "WSOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL": "JTO",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": "RAY",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RENDER",
}

_DS = "https://api.dexscreener.com"
_RC = "https://api.rugcheck.xyz/v1"
_GP = "https://api.gopluslabs.io/api/v1"
_MS_PER_HOUR = 1000 * 60 * 60


def _get_json(client: httpx.Client, url: str) -> Any | None:
    try:
        r = client.get(url)
        if r.status_code != httpx.codes.OK:
            return None
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def fetch_dex_profiles(client: httpx.Client, limit: int) -> list[str]:
    """Return fresh Solana mints from DexScreener's latest token profiles."""
    data = _get_json(client, f"{_DS}/token-profiles/latest/v1")
    mints: list[str] = []
    if isinstance(data, list):
        for item in data:
            if item.get("chainId") == "solana" and (addr := item.get("tokenAddress")):
                mints.append(addr)
    return mints[:limit]


def fetch_rugcheck_pool(client: httpx.Client, endpoint: str) -> list[str]:
    """Return mints from a RugCheck stats endpoint (verified / recent / new_tokens)."""
    data = _get_json(client, f"{_RC}/{endpoint}")
    if not isinstance(data, list):
        return []
    return [item["mint"] for item in data if isinstance(item, dict) and item.get("mint")]


def _best_pair(pairs: list[dict[str, Any]]) -> dict[str, Any] | None:
    sol = [p for p in pairs if p.get("chainId") == "solana"]
    if not sol:
        return None
    return max(sol, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0.0)


def dex_evidence(client: httpx.Client, mint: str, now_ms: int) -> dict[str, Any]:
    data = _get_json(client, f"{_DS}/latest/dex/tokens/{mint}")
    pairs = (data or {}).get("pairs") or []
    pair = _best_pair(pairs)
    if pair is None:
        return {"pair_found": False}
    created = pair.get("pairCreatedAt")
    txns = (pair.get("txns") or {}).get("h24") or {}
    sym = (pair.get("baseToken") or {}).get("symbol")
    return {
        "pair_found": True,
        "symbol": sym,
        "liquidity_usd": (pair.get("liquidity") or {}).get("usd"),
        "age_hours": round((now_ms - created) / _MS_PER_HOUR, 1) if created else None,
        "buys_24h": txns.get("buys"),
        "sells_24h": txns.get("sells"),
        "volume_24h_usd": (pair.get("volume") or {}).get("h24"),
        "price_change_24h_pct": (pair.get("priceChange") or {}).get("h24"),
    }


def rugcheck_evidence(client: httpx.Client, mint: str) -> dict[str, Any]:
    data = _get_json(client, f"{_RC}/tokens/{mint}/report/summary")
    if not isinstance(data, dict):
        return {"available": False}
    risks = [
        {"name": r.get("name"), "level": r.get("level")}
        for r in (data.get("risks") or [])
        if isinstance(r, dict)
    ]
    return {
        "available": True,
        "score_normalised": data.get("score_normalised"),
        "lp_locked_pct": data.get("lpLockedPct"),
        "risks": risks,
    }


def goplus_evidence(client: httpx.Client, mint: str) -> dict[str, Any]:
    data = _get_json(client, f"{_GP}/solana/token_security?contract_addresses={mint}")
    result = (data or {}).get("result") or {}
    info = result.get(mint) if isinstance(result, dict) else None
    if not isinstance(info, dict):
        return {"available": False}

    def status(key: str) -> str | None:
        v = info.get(key)
        return v.get("status") if isinstance(v, dict) else None

    return {
        "available": True,
        "mintable": status("mintable"),
        "freezable": status("freezable"),
        "closable": status("closable"),
        "balance_mutable_authority": status("balance_mutable_authority"),
        "transfer_fee_upgradable": status("transfer_fee_upgradable"),
        "non_transferable": status("non_transferable"),
    }


def gather(profiles_limit: int) -> list[dict[str, Any]]:
    now_ms = int(time.time() * 1000)
    packs: list[dict[str, Any]] = []
    with httpx.Client(
        timeout=15, follow_redirects=True, headers={"User-Agent": "langley-gather/1.0"}
    ) as client:
        # Build a diverse pool from several sources, deduped by first occurrence.
        # Priority order seeds the source_pool tag (curated/verified are trusted-legit
        # leaning; recent/new/profiles skew fresh-and-risky).
        sourced: list[tuple[str, str, str | None]] = [
            (m, "curated_legit", sym) for m, sym in CURATED_LEGIT.items()
        ]
        for mint in fetch_rugcheck_pool(client, "stats/verified"):
            sourced.append((mint, "rugcheck_verified", None))
        for mint in fetch_rugcheck_pool(client, "stats/recent"):
            sourced.append((mint, "rugcheck_recent", None))
        for mint in fetch_rugcheck_pool(client, "stats/new_tokens"):
            sourced.append((mint, "rugcheck_new", None))
        for mint in fetch_dex_profiles(client, profiles_limit):
            sourced.append((mint, "dex_profiles", None))

        seen: set[str] = set()
        pool: list[tuple[str, str, str | None]] = []
        for mint, src, sym in sourced:
            if mint not in seen:
                seen.add(mint)
                pool.append((mint, src, sym))

        for i, (mint, source_pool, hint_sym) in enumerate(pool, start=1):
            dex = dex_evidence(client, mint, now_ms)
            packs.append(
                {
                    "mint": mint,
                    "hint_symbol": hint_sym or dex.get("symbol"),
                    "source_pool": source_pool,
                    "dex": dex,
                    "rugcheck": rugcheck_evidence(client, mint),
                    "goplus": goplus_evidence(client, mint),
                }
            )
            print(f"  [{i}/{len(pool)}] {mint[:8]}… {source_pool} pair={dex.get('pair_found')}")
            time.sleep(0.15)  # be polite to free endpoints
    return packs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gather candidate-token evidence packs.")
    parser.add_argument("--profiles", type=int, default=25, help="Max DexScreener profile mints.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    packs = gather(args.profiles)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(packs, indent=2), encoding="utf-8")

    with_dex = sum(1 for p in packs if p["dex"].get("pair_found"))
    with_rc = sum(1 for p in packs if p["rugcheck"].get("available"))
    with_gp = sum(1 for p in packs if p["goplus"].get("available"))
    print(f"\nWrote {len(packs)} evidence packs -> {OUT_FILE}")
    print(f"  DexScreener pair found: {with_dex}/{len(packs)}")
    print(f"  RugCheck available:     {with_rc}/{len(packs)}")
    print(f"  GoPlus available:       {with_gp}/{len(packs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
