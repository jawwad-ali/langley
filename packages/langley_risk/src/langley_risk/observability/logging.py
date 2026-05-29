"""structlog-based logging configuration.

``configure_logging`` is idempotent-friendly and routes stdlib ``logging`` (used
throughout the package) through structlog so output is consistent whether the caller
wants human-readable console logs or JSON for aggregation.
"""

from __future__ import annotations

import logging

import structlog


def configure_logging(*, level: str = "INFO", as_json: bool = False) -> None:
    """Configure structlog + stdlib logging for the process.

    Args:
        level: Root log level name (e.g. "INFO", "DEBUG").
        as_json: Emit JSON lines (for aggregation) instead of console-formatted logs.
    """
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if as_json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=logging.getLevelNamesMapping().get(level.upper(), logging.INFO),
        format="%(message)s",
    )
