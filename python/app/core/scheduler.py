"""APScheduler batch runner (Q4). Embedded in the FastAPI process; runs the ETL
batch on a daily cron. Disabled by default in tests (no import side effects)."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.api import _run_batch_task
from app.core.logging import get_logger

log = get_logger("scheduler")


def start_scheduler() -> BackgroundScheduler:  # pragma: no cover - runtime only
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_run_batch_task, "cron", hour=6, id="daily_batch", replace_existing=True)
    sched.start()
    log.info("scheduler_started", job="daily_batch", cron="hour=6")
    return sched
