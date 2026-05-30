"""Assign PROVISIONAL labels to gathered evidence packs (deterministic first pass).

These labels are proposals, not ground truth. Rationale:
- RugCheck's risk flags are noisy (they fire on legit majors too), so we only label
  from *decisive* signals and otherwise EXCLUDE rather than guess.
- Each label is tagged with ``danger_visibility``: whether the danger is visible in the
  DexScreener data the agent actually sees, or only in contract data it cannot see.
  This lets the eval fairly separate "agent should catch this" from "agent should
  abstain; needs a contract-data provider".

Output: evals/golden_v2/provisional.json — to be adversarially audited by the workflow
before anything is trusted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EV_DIR = Path(__file__).resolve().parents[1] / "evals" / "golden_v2"
EVIDENCE = EV_DIR / "evidence.json"
OUT = EV_DIR / "provisional.json"

TRUSTED_POOLS = {"curated_legit", "rugcheck_verified"}
RUG_MAX_LIQ = 1_000.0
SAFE_MIN_LIQ = 50_000.0
SAFE_MIN_AGE_H = 168.0
HONEYPOT_MIN_BUYS = 20


def _label_one(pack: dict[str, Any]) -> dict[str, Any]:
    dex = pack["dex"]
    rc = pack["rugcheck"]
    pool = pack["source_pool"]
    liq = dex.get("liquidity_usd")
    age = dex.get("age_hours")
    buys = dex.get("buys_24h") or 0
    sells = dex.get("sells_24h")
    risk_names = " ".join((r.get("name") or "").lower() for r in (rc.get("risks") or []))

    def out(label: str, subtype: str, visibility: str, conf: float, why: str) -> dict[str, Any]:
        return {
            "mint": pack["mint"],
            "hint_symbol": pack.get("hint_symbol"),
            "source_pool": pool,
            "provisional_label": label,
            "label_subtype": subtype,
            "danger_visibility": visibility,
            "provisional_confidence": conf,
            "rationale": why,
        }

    if not dex.get("pair_found"):
        return out("exclude", "no_market", "n/a", 0.3, "No DEX pair — agent has no data to judge.")

    # Decisive, DexScreener-VISIBLE danger (the agent should catch these).
    if buys > HONEYPOT_MIN_BUYS and sells == 0:
        return out(
            "unsafe",
            "honeypot",
            "dexscreener_visible",
            0.8,
            f"{buys} buys with 0 sells in 24h — one-sided trading (honeypot pattern).",
        )
    if liq is not None and liq < RUG_MAX_LIQ and (buys + (sells or 0)) > 0:
        return out(
            "unsafe",
            "low_liquidity",
            "dexscreener_visible",
            0.8,
            f"Near-zero liquidity (${liq:,.0f}) with live trading — rug/exit-scam risk.",
        )

    # Trusted-source healthy market → legit.
    if (
        pool in TRUSTED_POOLS
        and liq is not None
        and liq >= SAFE_MIN_LIQ
        and (age is not None and age >= SAFE_MIN_AGE_H)
    ):
        return out(
            "safe",
            "established",
            "n/a",
            0.8,
            f"Trusted/verified token, deep liquidity (${liq:,.0f}), age {age:,.0f}h.",
        )

    # Contract-ONLY danger the agent cannot see from DexScreener (should abstain).
    if "rugged" in risk_names:
        return out(
            "unsafe",
            "creator_rug_history",
            "contract_only",
            0.6,
            "RugCheck flags creator history of rugged tokens (not visible on DexScreener).",
        )

    return out(
        "exclude",
        "ambiguous",
        "n/a",
        0.3,
        "Mixed/insufficient signals — excluded rather than guess.",
    )


def main() -> int:
    packs = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    labels = [_label_one(p) for p in packs]
    OUT.write_text(json.dumps(labels, indent=2), encoding="utf-8")

    dist: dict[str, int] = {}
    vis: dict[str, int] = {}
    for label in labels:
        key = f"{label['provisional_label']}/{label['label_subtype']}"
        dist[key] = dist.get(key, 0) + 1
        vis[label["danger_visibility"]] = vis.get(label["danger_visibility"], 0) + 1
    print(f"Wrote {len(labels)} provisional labels -> {OUT}\n")
    print("By label/subtype:")
    for k, v in sorted(dist.items()):
        print(f"  {k:<32} {v}")
    print("\nBy danger visibility:")
    for k, v in sorted(vis.items()):
        print(f"  {k:<22} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
