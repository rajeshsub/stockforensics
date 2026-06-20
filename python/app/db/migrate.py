"""Create all tables (idempotent). Run by `make bootstrap`."""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from app.db.engine import get_engine
from app.db.models import Base

# Columns added after the initial schema: {table: {column: SQLite DDL type}}.
# create_all() won't ALTER existing tables, so add them by hand (idempotent).
_ADDED_COLUMNS = {
    "company_scores": {"citations": "JSON", "thinking": "JSON", "composite_narrative": "VARCHAR"}
}


def _ensure_columns(engine: Engine) -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for table, cols in _ADDED_COLUMNS.items():
        if table not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        with engine.begin() as conn:
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def migrate(path: str | None = None) -> None:
    engine = get_engine(path)
    Base.metadata.create_all(engine)
    _ensure_columns(engine)


def main() -> None:  # pragma: no cover - CLI entry
    from app.core.config import get_settings
    from app.core.logging import configure_logging, get_logger

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    migrate()
    get_logger("migrate").info("migrated", path=s.sqlite_path)


if __name__ == "__main__":  # pragma: no cover
    main()
