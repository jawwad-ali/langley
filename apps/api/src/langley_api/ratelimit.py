"""Lightweight, dependency-free request guardrails for the public demo.

Each analysis spends real OpenAI + Helius budget, so a public endpoint needs two
protections: a per-client rate limit (stop one visitor hammering it) and a global
daily cap (bound total spend per day). In-memory and single-process — fine for a demo;
swap for Redis if this ever scales out.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


def _empty_hits() -> dict[str, deque[float]]:
    """Typed default factory (keeps Pyright strict happy)."""
    return {}


class RateLimitError(Exception):
    """Raised when a request exceeds the per-client or global limit."""

    def __init__(self, retry_after_s: int, reason: str) -> None:
        self.retry_after_s = retry_after_s
        self.reason = reason
        super().__init__(reason)


@dataclass
class RateLimiter:
    """Per-client sliding window + a global daily cap."""

    per_client_limit: int = 5
    per_client_window_s: int = 60
    daily_cap: int = 200
    _hits: dict[str, deque[float]] = field(default_factory=_empty_hits)
    _day: int = 0
    _day_count: int = 0

    def check(self, client: str, *, now: float | None = None) -> None:
        """Record a request from ``client``; raise RateLimitError if over a limit."""
        now = time.time() if now is None else now

        # Global daily cap (UTC day bucket).
        day = int(now // 86_400)
        if day != self._day:
            self._day, self._day_count = day, 0
        if self._day_count >= self.daily_cap:
            raise RateLimitError(86_400, "Daily demo limit reached — please try again tomorrow.")

        # Per-client sliding window.
        window = self._hits.setdefault(client, deque())
        cutoff = now - self.per_client_window_s
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= self.per_client_limit:
            retry = int(window[0] + self.per_client_window_s - now) + 1
            raise RateLimitError(retry, "Too many requests — slow down a moment.")

        window.append(now)
        self._day_count += 1
