"""Assemble the golden_v2 dataset from audited labels + synthetic controls.

Real tokens (audited, both skeptics agreed): records a live DexScreener snapshot
fixture for each. Synthetic controls (visible-danger fixtures reused from v1): copied
in so the eval can also measure DexScreener-visible detection, clearly flagged.

Outputs evals/golden_v2/golden_v2.jsonl + evals/golden_v2/fixtures/*.json.
Run: uv run python packages/langley_risk/scripts/assemble_v2.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from langley_risk.config import get_settings, load_env_file
from langley_risk.errors import ProviderError
from langley_risk.evals.recorded_provider import write_snapshot_fixture
from langley_risk.providers.factory import get_provider

PKG = Path(__file__).resolve().parents[1]
V2_DIR = PKG / "evals" / "golden_v2"
FIXTURES_V2 = V2_DIR / "fixtures"
V1_FIXTURES = PKG / "evals" / "fixtures" / "dexscreener"

# Audited real tokens (both skeptics agreed). (id, mint, label, visibility, subtype)
REAL: list[tuple[str, str, str, str, str]] = [
    ("sol", "So11111111111111111111111111111111111111112", "safe", "na", "bluechip"),
    ("usdc", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "safe", "na", "stablecoin"),
    ("bonk", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "safe", "na", "established"),
    ("jup", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "safe", "na", "established"),
    ("jto", "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL", "safe", "na", "established"),
    ("wif", "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "safe", "na", "established"),
    ("ray", "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "safe", "na", "established"),
    ("pyth", "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3", "safe", "na", "established"),
    ("render", "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof", "safe", "na", "established"),
    (
        "evilfish",
        "89PZ7tzJ1bkWJFgrno7xdvk7u5MTfcAKu65S9YBTpump",
        "unsafe",
        "contract_only",
        "creator_rug_history",
    ),
    (
        "greedani",
        "GeB8t9ZYfCa2PCyw2XgWiDBB1WMmC6nrPUwTthAkpump",
        "unsafe",
        "contract_only",
        "creator_rug_history",
    ),
]

# Synthetic controls for DexScreener-VISIBLE danger. (id, source_fixture, subtype)
SYNTHETIC: list[tuple[str, str, str]] = [
    ("syn_rug", "rug_low_liquidity.json", "low_liquidity"),
    ("syn_honeypot", "honeypot_no_sells.json", "honeypot"),
]


async def _record_real(rows: list[dict[str, Any]]) -> None:
    provider = get_provider(get_settings())
    try:
        for row_id, mint, label, visibility, subtype in REAL:
            try:
                snapshot = await provider.get_market_snapshot(mint)
            except ProviderError as exc:
                print(f"  SKIP {row_id} ({mint[:8]}…): {exc}")
                continue
            write_snapshot_fixture(snapshot, FIXTURES_V2 / f"{row_id}.json")
            rows.append(
                {
                    "id": row_id,
                    "query": mint,
                    "label": label,
                    "danger_visibility": visibility,
                    "source": "real",
                    "subtype": subtype,
                    "fixture": f"{row_id}.json",
                }
            )
            print(f"  recorded {row_id} ({label}/{visibility})")
    finally:
        await provider.aclose()


def _copy_synthetic(rows: list[dict[str, Any]]) -> None:
    for row_id, src, subtype in SYNTHETIC:
        shutil.copyfile(V1_FIXTURES / src, FIXTURES_V2 / f"{row_id}.json")
        rows.append(
            {
                "id": row_id,
                "query": json.loads((FIXTURES_V2 / f"{row_id}.json").read_text("utf-8"))["query"],
                "label": "unsafe",
                "danger_visibility": "dexscreener_visible",
                "source": "synthetic",
                "subtype": subtype,
                "fixture": f"{row_id}.json",
            }
        )
        print(f"  copied  {row_id} (unsafe/dexscreener_visible)")


def main() -> int:
    load_env_file()
    print(f"Recording with provider = {get_settings().provider.value}")
    FIXTURES_V2.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    asyncio.run(_record_real(rows))
    _copy_synthetic(rows)
    out = V2_DIR / "golden_v2.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"\nWrote {len(rows)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
