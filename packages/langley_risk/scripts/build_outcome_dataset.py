"""Build an OUTCOME-verified candidate dataset from real Solana tokens.

Labels by *what actually happened* to a token over its life, using the insight that a
token's age + current state reveals its fate (free data, no paid history API):

- "died" (unsafe):    old enough to be settled, but now near-zero liquidity AND dead
                      trading -> it rugged/was abandoned; a holder would have lost money.
- "survived" (safe):  old enough to be settled, and still deep liquidity + active
                      two-sided trading -> it lasted.
- excluded:           too young (outcome not yet settled) or ambiguous middle ground.

We aggregate across ALL of a token's pairs (so a single stale pair can't make a live
token look dead) and take the oldest pair as the token's age.

Output: evals/golden_v3/candidates.json (+ distribution summary).
Run: uv run python packages/langley_risk/scripts/build_outcome_dataset.py
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

OUT_DIR = Path(__file__).resolve().parents[1] / "evals" / "golden_v3"
OUT_FILE = OUT_DIR / "candidates.json"
_DS = "https://api.dexscreener.com"
_MS_PER_HOUR = 1000 * 60 * 60

# Broad terms to surface a diverse pool (names/symbols matched by DexScreener search).
SEARCH_TERMS = [
    "inu",
    "pepe",
    "doge",
    "cat",
    "ai",
    "moon",
    "trump",
    "elon",
    "bonk",
    "sol",
    "baby",
    "shiba",
    "wif",
    "meme",
    "pump",
    "floki",
    "mog",
    "wojak",
    "chad",
    "gem",
]

# Outcome rubric thresholds.
SETTLED_AGE_H = 720.0  # 30 days — old enough for the outcome to be settled
DEAD_VOLUME_USD = 500.0  # below this (24h) = effectively no one trades it = abandoned
DEAD_MAX_LIQUIDITY_USD = 25_000.0  # ...and shallow — together = died (holder lost out)
ALIVE_LIQUIDITY_USD = 50_000.0
ALIVE_VOLUME_USD = 10_000.0

# Substrings that mark a token as a major/wrapped/staked/stable asset rather than a
# memecoin — for these, low trading volume is NOT a death signal, so we don't call them
# "died" (we exclude them rather than mislabel).
NON_MEMECOIN_HINTS = (
    "usd",
    "dai",
    "wrapped",
    "wsol",
    "weth",
    "wbtc",
    "btc",
    "eth",
    "staked",
    "msol",
    "jitosol",
    "bsol",
    "lst",
    "bond",
)


def _looks_major(agg: dict[str, Any]) -> bool:
    text = f"{agg.get('symbol') or ''} {agg.get('name') or ''}".lower()
    return any(hint in text for hint in NON_MEMECOIN_HINTS)


def _search(client: httpx.Client, term: str) -> list[dict[str, Any]]:
    try:
        r = client.get(f"{_DS}/latest/dex/search", params={"q": term})
        if r.status_code != httpx.codes.OK:
            return []
        pairs = r.json().get("pairs") or []
        return [p for p in pairs if isinstance(p, dict) and p.get("chainId") == "solana"]
    except (httpx.HTTPError, ValueError):
        return []


def _aggregate(pairs: list[dict[str, Any]], now_ms: int) -> dict[str, Any]:
    liq = sum((p.get("liquidity") or {}).get("usd") or 0.0 for p in pairs)
    vol = sum((p.get("volume") or {}).get("h24") or 0.0 for p in pairs)
    buys = sum(((p.get("txns") or {}).get("h24") or {}).get("buys") or 0 for p in pairs)
    sells = sum(((p.get("txns") or {}).get("h24") or {}).get("sells") or 0 for p in pairs)
    created = [p.get("pairCreatedAt") for p in pairs if p.get("pairCreatedAt")]
    age_h = (now_ms - min(created)) / _MS_PER_HOUR if created else None
    base = pairs[0].get("baseToken") or {}
    return {
        "token_address": base.get("address"),
        "symbol": base.get("symbol"),
        "name": base.get("name"),
        "liquidity_usd": round(liq, 2),
        "volume_24h_usd": round(vol, 2),
        "buys_24h": buys,
        "sells_24h": sells,
        "age_hours": round(age_h, 1) if age_h is not None else None,
        "pair_count": len(pairs),
    }


def _label(agg: dict[str, Any]) -> tuple[str, str]:
    """Return (label, reason) from the outcome rubric."""
    age = agg["age_hours"]
    liq = agg["liquidity_usd"]
    vol = agg["volume_24h_usd"]
    if age is None or age < SETTLED_AGE_H:
        return "exclude", "too young — outcome not yet settled"
    if vol < DEAD_VOLUME_USD and liq < DEAD_MAX_LIQUIDITY_USD:
        if _looks_major(agg):
            return "exclude", "major/wrapped/stable asset — low volume is not a death signal"
        return "died", f"abandoned at {age:.0f}h (vol ${vol:,.0f}/24h, liq ${liq:,.0f})"
    if liq >= ALIVE_LIQUIDITY_USD and vol >= ALIVE_VOLUME_USD and agg["sells_24h"] > 0:
        return "survived", f"alive at {age:.0f}h (liq ${liq:,.0f}, vol ${vol:,.0f}/24h)"
    return "exclude", "ambiguous middle ground"


def _to_row(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    outcome = candidate["outcome_label"]
    return {
        "id": f"{outcome}-{index:03d}",
        "query": candidate["token_address"],
        "outcome": outcome,
        "label": "unsafe" if outcome == "died" else "safe",
        "symbol": candidate["symbol"],
        "age_hours": candidate["age_hours"],
        "liquidity_usd": candidate["liquidity_usd"],
        "volume_24h_usd": candidate["volume_24h_usd"],
        "source": "real_outcome",
        "reason": candidate["reason"],
    }


def _split(labeled: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministic, label-stratified ~70/30 train/test split (every 3rd row -> test)."""
    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []
    counter = 0
    for outcome in ("died", "survived"):
        group = sorted(
            (c for c in labeled if c["outcome_label"] == outcome), key=lambda c: c["token_address"]
        )
        for i, candidate in enumerate(group):
            row = _to_row(candidate, counter)
            counter += 1
            (test if i % 3 == 0 else train).append(row)
    return train, test


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def main() -> int:
    now_ms = int(time.time() * 1000)
    by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with httpx.Client(timeout=15, headers={"User-Agent": "langley-outcomes/1.0"}) as client:
        for term in SEARCH_TERMS:
            for pair in _search(client, term):
                addr = (pair.get("baseToken") or {}).get("address")
                if addr:
                    by_token[addr].append(pair)
            time.sleep(0.2)

    candidates: list[dict[str, Any]] = []
    for pairs in by_token.values():
        agg = _aggregate(pairs, now_ms)
        if not agg["token_address"]:
            continue
        label, reason = _label(agg)
        candidates.append({**agg, "outcome_label": label, "reason": reason})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(candidates, indent=2), encoding="utf-8")

    labeled = [c for c in candidates if c["outcome_label"] in ("died", "survived")]
    train, test = _split(labeled)
    _write_jsonl(train, OUT_DIR / "train.jsonl")
    _write_jsonl(test, OUT_DIR / "test.jsonl")

    dist: dict[str, int] = defaultdict(int)
    for c in candidates:
        dist[c["outcome_label"]] += 1
    print(f"Collected {len(by_token)} unique tokens -> {len(candidates)} candidates\n")
    print("Outcome distribution:")
    for label in ("survived", "died", "exclude"):
        print(f"  {label:<10} {dist[label]}")
    print(f"\nLabeled set: {len(labeled)}  ->  train={len(train)}  test(held-out)={len(test)}")
    print(f"Wrote: {OUT_DIR / 'train.jsonl'}\n       {OUT_DIR / 'test.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
