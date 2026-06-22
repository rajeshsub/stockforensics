"""Seed the DB with the snapshot universe using offline fixture scoring data.
Company list comes from data/universe/sp500.csv; SEC/market scoring uses fixtures
so startup is fast and offline. Live scoring runs on demand in analyze.py."""

from __future__ import annotations

from app.core.clients import build_adapters
from app.core.config import get_settings
from app.db.engine import session_scope
from app.db.migrate import migrate
from app.pipeline.runner import run_batch


def seed(path: str | None = None) -> int:
    s = get_settings()
    migrate(path)
    # Start with all fixture adapters (offline, deterministic), then override
    # just the universe so we get the full snapshot company list.
    a = build_adapters(s, force_fixtures=True)
    try:
        from app.adapters.universe_client import ISharesUniverseClient

        a.universe = ISharesUniverseClient(s)
    except Exception:
        pass  # falls back to fixture universe (AAPL + MSFT) if snapshot unavailable
    with session_scope(path) as session:
        return run_batch(a, session)


def main() -> None:  # pragma: no cover - CLI entry
    from app.core.logging import configure_logging, get_logger

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    n = seed()
    get_logger("seed").info("seeded", companies=n)


if __name__ == "__main__":  # pragma: no cover
    main()
