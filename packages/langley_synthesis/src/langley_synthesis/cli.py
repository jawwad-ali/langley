"""Command-line entrypoint: ``python -m langley_synthesis <query>``.

Thin — parse args, configure observability, call ``synthesize_token``, render the fused
report. Reuses langley_risk's env-loading and logging.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from langley_risk.config import get_settings, load_env_file
from langley_risk.errors import LangleyRiskError
from langley_risk.observability.logging import configure_logging
from langley_risk.observability.tracing import install_tracing
from langley_synthesis.domain.report import IntelligenceReport
from langley_synthesis.service.orchestrate import synthesize_token


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="langley-synthesis",
        description="Fused multi-agent intelligence report for a Solana token.",
    )
    parser.add_argument("query", help="Solana mint address or token symbol/name.")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    return parser.parse_args(argv)


def _render(report: IntelligenceReport) -> str:
    lines = [
        f"Token:    {report.token_symbol or '?'} ({report.token_address})",
        f"Verdict:  {report.verdict.value.upper()}  (confidence {report.confidence:.0%})",
        f"Agents:   {', '.join(report.contributing_agents)}  ·  data: {report.data_provider}",
        f"Agreement: {report.agreement.value}",
        "",
        f"  {report.headline}",
        "",
        report.briefing,
    ]
    if report.key_points:
        lines.append("\nKey points:")
        lines += [f"  - {p}" for p in report.key_points]
    lines.append(
        f"\nUnderlying: {len(report.risk_signals)} risk signal(s), "
        f"{len(report.forensic_findings)} forensic finding(s)."
    )
    return "\n".join(lines)


async def _run(query: str, *, as_json: bool) -> int:
    report = await synthesize_token(query)
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
