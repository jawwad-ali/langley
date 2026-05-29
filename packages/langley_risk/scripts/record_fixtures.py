"""One-off: fetch live DexScreener data and write snapshot fixtures.

Run manually (never in CI) to (re)create eval/test fixtures from real data:

    uv run python packages/langley_risk/scripts/record_fixtures.py \
        So11111111111111111111111111111111111111112 bluechip_deep_liquidity.json

Writes a MarketSnapshot JSON under evals/fixtures/dexscreener/. Review the output and
label it in golden_v1.jsonl before relying on it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from langley_risk.config import get_settings
from langley_risk.evals.dataset import FIXTURES_DIR
from langley_risk.evals.recorded_provider import write_snapshot_fixture
from langley_risk.providers.factory import get_provider


async def _record(query: str, filename: str) -> None:
    provider = get_provider(get_settings())
    try:
        snapshot = await provider.get_market_snapshot(query)
    finally:
        await provider.aclose()
    out = FIXTURES_DIR / filename
    write_snapshot_fixture(snapshot, out)
    print(f"wrote {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a DexScreener snapshot fixture.")
    parser.add_argument("query", help="Mint address or symbol to fetch.")
    parser.add_argument("filename", help="Output fixture filename, e.g. token.json.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    asyncio.run(_record(args.query, args.filename))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
