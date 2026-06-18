"""US market-hours gate for live polling (Q5). Regular NYSE/Nasdaq session only:
weekdays, 09:30–16:00 America/New_York, minus holidays. Holiday set is explicit +
extendable (no extra dependency)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
OPEN = time(9, 30)
CLOSE = time(16, 0)

# US equity-market holidays (extend per year as needed).
HOLIDAYS: set[date] = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}


def now_ny(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(NY)


def is_trading_day(now: datetime | None = None) -> bool:
    n = now_ny(now)
    return n.weekday() < 5 and n.date() not in HOLIDAYS


def is_market_open(now: datetime | None = None) -> bool:
    n = now_ny(now)
    return is_trading_day(n) and OPEN <= n.time() < CLOSE
