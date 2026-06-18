"""Live universe client: reads the vendored iShares snapshot, auto-refreshing when
older than the TTL; falls back to the existing snapshot on fetch failure (Q8)."""

from __future__ import annotations

from app.adapters.protocols import Constituent
from app.core.config import Settings
from app.core.logging import get_logger
from app.pipeline.universe import (
    DEFAULT_SNAPSHOT,
    load_snapshot,
    refresh_snapshot,
    snapshot_age_hours,
)

log = get_logger("universe")


class ISharesUniverseClient:
    def __init__(self, settings: Settings, path: str = DEFAULT_SNAPSHOT) -> None:
        self._s = settings
        self._path = path

    def fetch_constituents(self) -> list[Constituent]:
        age = snapshot_age_hours(self._path)
        if self._s.universe_auto_refresh and (age is None or age > self._s.universe_ttl_hours):
            try:
                n = refresh_snapshot(self._path)
                log.info("universe_refreshed", count=n)
            except Exception as e:  # fetch failed -> use existing snapshot (Q8)
                log.warning("universe_refresh_failed", error=str(e))
        return [
            Constituent(
                ticker=row["ticker"],
                name=row.get("name", ""),
                sector=row.get("sector") or None,
            )
            for row in load_snapshot(self._path)
        ]
