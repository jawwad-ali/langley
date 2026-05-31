"""Unit tests for the demo rate limiter (deterministic via injected clock)."""

from __future__ import annotations

import pytest

from langley_api.ratelimit import RateLimiter, RateLimitError


class TestPerClientLimit:
    def test_allows_up_to_limit_then_blocks(self) -> None:
        rl = RateLimiter(per_client_limit=2, per_client_window_s=60, daily_cap=100)
        rl.check("1.1.1.1", now=1000.0)
        rl.check("1.1.1.1", now=1001.0)
        with pytest.raises(RateLimitError, match="Too many requests"):
            rl.check("1.1.1.1", now=1002.0)

    def test_window_slides(self) -> None:
        rl = RateLimiter(per_client_limit=1, per_client_window_s=60, daily_cap=100)
        rl.check("1.1.1.1", now=1000.0)
        with pytest.raises(RateLimitError):
            rl.check("1.1.1.1", now=1030.0)
        rl.check("1.1.1.1", now=1061.0)  # past the window -> allowed again

    def test_clients_are_independent(self) -> None:
        rl = RateLimiter(per_client_limit=1, per_client_window_s=60, daily_cap=100)
        rl.check("1.1.1.1", now=1000.0)
        rl.check("2.2.2.2", now=1000.0)  # different client, not blocked


class TestDailyCap:
    def test_global_cap_blocks_regardless_of_client(self) -> None:
        rl = RateLimiter(per_client_limit=100, per_client_window_s=60, daily_cap=2)
        rl.check("a", now=1000.0)
        rl.check("b", now=1000.0)
        with pytest.raises(RateLimitError, match="Daily demo limit"):
            rl.check("c", now=1000.0)
