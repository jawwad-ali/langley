"""Command-line entrypoint: ``python -m langley_onchain <query>``.

Thin — parse args, configure observability, call ``analyze_onchain``, render the profile.
Reuses langley_risk's env-loading and logging so a root ``.env`` works the same way.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from langley_onchain.domain.report import ForensicsReport
from langley_onchain.service.analyze import analyze_onchain
from langley_risk.config import get_settings, load_env_file
from langley_risk.errors import LangleyRiskError
from langley_risk.observability.logging import configure_logging
from langley_risk.observability.tracing import install_tracing


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="langley-onchain",
        description="Neutral on-chain forensic profile of a Solana token.",
    )
    parser.add_argument("query", help="Solana mint address or token symbol/name.")
    parser.add_argument("--json", action="store_true", help="Emit the profile as JSON.")
    return parser.parse_args(argv)


def _render(report: ForensicsReport) -> str:
    lines = [
        f"Token:    {report.token_symbol or '?'} ({report.token_address})",
        f"Data:     {report.data_provider}",
        "",
        report.profile_summary,
    ]
    if report.findings:
        lines.append("\nFindings:")
        for f in report.findings:
            cites = ", ".join(f"{e.field}={e.observed_value}" for e in f.evidence)
            lines.append(f"  [{f.dimension.value}] {f.observation}  ({cites})")
    return "\n".join(lines)


async def _run(query: str, *, as_json: bool) -> int:
    report = await analyze_onchain(query)
    print(report.model_dump_json(indent=2) if as_json else _render(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Console entrypoint. Returns a process exit code."""
    load_env_file()
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    settings = get_settings()
    configure_logging(level=settings.log_level, as_json=settings.log_json)
    install_tracing()
    try:
        return asyncio.run(_run(args.query, as_json=args.json))
    except LangleyRiskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
