"""Command-line entrypoint: ``python -m langley_risk <query>`` / ``langley-risk <query>``.

Thin by design — parse args, configure observability, call ``analyze_token``, render
the report. All logic lives in the service layer.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from langley_risk.config import get_settings, load_env_file
from langley_risk.domain.report import TokenRiskReport
from langley_risk.errors import LangleyRiskError
from langley_risk.observability.logging import configure_logging
from langley_risk.observability.tracing import install_tracing
from langley_risk.service.analyze import analyze_token


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="langley-risk",
        description="Assess the risk of a Solana token (Risk Guardian).",
    )
    parser.add_argument("query", help="Solana mint address or token symbol/name.")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    return parser.parse_args(argv)


def _render(report: TokenRiskReport) -> str:
    lines = [
        f"Token:      {report.token_symbol or '?'} ({report.token_address})",
        f"Verdict:    {report.verdict.value.upper()}  (confidence {report.confidence:.0%})",
        f"Data:       {report.data_provider}",
        "",
        report.summary,
    ]
    if report.abstain_reason:
        lines += ["", f"Abstain reason: {report.abstain_reason}"]
    if report.signals:
        lines.append("\nSignals:")
        for s in report.signals:
            cites = ", ".join(f"{e.field}={e.observed_value}" for e in s.evidence)
            lines.append(f"  [{s.level.value}] {s.category.value}: {s.title}  ({cites})")
    return "\n".join(lines)


async def _run(query: str, *, as_json: bool) -> int:
    report = await analyze_token(query)
    output = report.model_dump_json(indent=2) if as_json else _render(report)
    print(output)
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
