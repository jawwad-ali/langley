"""A ``DataProvider`` that replays recorded ``MarketSnapshot`` fixtures.

Used by the eval harness for deterministic, network-free runs: each golden case names
a fixture file containing a pre-recorded snapshot (produced by ``scripts/record_fixtures.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

from langley_risk.domain.market import MarketSnapshot
from langley_risk.errors import TokenNotFoundError


class RecordedProvider:
    """Serves snapshots from a fixtures directory, keyed by fixture filename."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._dir = fixtures_dir
        self._by_query: dict[str, MarketSnapshot] = {}

    def load_fixture(self, filename: str) -> MarketSnapshot:
        """Load (and cache by its query) a snapshot fixture, returning it."""
        path = self._dir / filename
        snapshot = MarketSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        self._by_query[snapshot.query] = snapshot
        return snapshot

    @property
    def name(self) -> str:
        return "recorded"

    async def get_market_snapshot(self, query: str) -> MarketSnapshot:
        snapshot = self._by_query.get(query)
        if snapshot is None:
            # Single-fixture convenience: when exactly one snapshot is loaded, serve it
            # regardless of the exact query string the agent passed.
            if len(self._by_query) == 1:
                return next(iter(self._by_query.values()))
            raise TokenNotFoundError(query)
        return snapshot

    async def aclose(self) -> None:
        return None


def write_snapshot_fixture(snapshot: MarketSnapshot, path: Path) -> None:
    """Persist a snapshot as a fixture file (used by the recording script)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.model_dump(), indent=2), encoding="utf-8")
