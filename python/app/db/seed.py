"""Seed the DB with deterministic fixture data so the API serves real-looking
results immediately after `make bootstrap`; fully offline, no keys (Q7)."""

from __future__ import annotations

from app.core.clients import build_adapters
from app.core.config import get_settings
from app.db.engine import session_scope
from app.db.migrate import migrate
from app.pipeline.runner import run_batch


def seed(path: str | None = None, force_fixtures: bool = True) -> int:
    s = get_settings()
    migrate(path)
    with session_scope(path) as session:
        return run_batch(
            build_adapters(s, force_fixtures=force_fixtures),
            session,
        )


def main() -> None:  # pragma: no cover - CLI entry
    from app.core.logging import configure_logging, get_logger

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    n = seed()
    get_logger("seed").info("seeded", companies=n)


if __name__ == "__main__":  # pragma: no cover
    main()
