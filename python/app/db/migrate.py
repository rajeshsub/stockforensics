"""Create all tables (idempotent). Run by `make bootstrap`."""

from __future__ import annotations

from app.db.engine import get_engine
from app.db.models import Base


def migrate(path: str | None = None) -> None:
    Base.metadata.create_all(get_engine(path))


def main() -> None:  # pragma: no cover - CLI entry
    from app.core.config import get_settings
    from app.core.logging import configure_logging, get_logger

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    migrate()
    get_logger("migrate").info("migrated", path=s.sqlite_path)


if __name__ == "__main__":  # pragma: no cover
    main()
