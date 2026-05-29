"""Bridge the OpenAI Agents SDK tracing into our structured logger.

The SDK emits a trace per agent run with spans for each LLM/tool call. We forward
those span lifecycle events into structlog so they show up alongside our own logs
(and can later be pointed at OTel/Logfire). For deterministic, network-free eval and
test runs, ``disable_tracing`` turns the SDK tracing off entirely.
"""

from __future__ import annotations

from typing import Any

import structlog
from agents import add_trace_processor, set_tracing_disabled
from agents.tracing import Span, Trace, TracingProcessor

_log = structlog.get_logger("langley_risk.trace")


class StructlogTracingProcessor(TracingProcessor):
    """Forward Agents SDK trace/span events into structlog."""

    def on_trace_start(self, trace: Trace) -> None:
        _log.debug("trace.start", trace_id=trace.trace_id, name=trace.name)

    def on_trace_end(self, trace: Trace) -> None:
        _log.info("trace.end", trace_id=trace.trace_id, name=trace.name)

    def on_span_start(self, span: Span[Any]) -> None:
        _log.debug("span.start", span_id=span.span_id, type=type(span.span_data).__name__)

    def on_span_end(self, span: Span[Any]) -> None:
        error = getattr(span, "error", None)
        _log.debug(
            "span.end",
            span_id=span.span_id,
            type=type(span.span_data).__name__,
            error=str(error) if error else None,
        )

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None


def install_tracing() -> None:
    """Register the structlog tracing processor (additive to SDK defaults)."""
    add_trace_processor(StructlogTracingProcessor())


def disable_tracing() -> None:
    """Disable SDK tracing entirely — used by offline evals and tests."""
    set_tracing_disabled(True)
