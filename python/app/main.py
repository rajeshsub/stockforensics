"""ASGI entry: `uvicorn app.main:app`. Wires logging + embedded scheduler."""

from __future__ import annotations

from app.core.api import app
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.migrate import migrate


@app.on_event("startup")
def _startup() -> None:  # pragma: no cover - runtime only
    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    log = get_logger("startup")

    try:
        migrate()
    except Exception:
        log.exception("migrate_failed")

    try:
        from app.core.scheduler import start_scheduler

        start_scheduler()
    except Exception:
        log.exception("scheduler_start_failed")
