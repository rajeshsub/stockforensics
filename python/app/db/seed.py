"""DB seeding utilities.

seed()          - fixture-only, offline, used by tests and make bootstrap.
seed_extended() - top-10 S&P 500 with real SEC XBRL + YFinance market data.
                  No API key required. SEC companyfacts data is valid for ~1 year
                  (annual 10-K cadence); staleness is checked in _boot_db before
                  calling this.
"""

from __future__ import annotations

from app.core.clients import build_adapters
from app.core.config import get_settings
from app.db.engine import session_scope
from app.db.migrate import migrate
from app.pipeline.runner import run_batch

# Top-10 S&P 500 by market cap (snapshot order used as tiebreak when market data
# is unavailable; re-ranked by live YFinance market cap inside run_batch).
_TOP10 = [
    ("AAPL", "Apple Inc", "Information Technology"),
    ("MSFT", "Microsoft Corp", "Information Technology"),
    ("NVDA", "NVIDIA Corp", "Information Technology"),
    ("AMZN", "Amazon.com Inc", "Consumer Discretionary"),
    ("GOOGL", "Alphabet Inc", "Communication Services"),
    ("META", "Meta Platforms Inc", "Communication Services"),
    ("TSLA", "Tesla Inc", "Consumer Discretionary"),
    ("BRK.B", "Berkshire Hathaway", "Financials"),
    ("AVGO", "Broadcom Inc", "Information Technology"),
    ("JPM", "JPMorgan Chase & Co", "Financials"),
]


def seed(path: str | None = None) -> int:
    """Fixture-only seed: AAPL + MSFT with full deterministic scores. Used by tests."""
    s = get_settings()
    migrate(path)
    with session_scope(path) as session:
        return run_batch(build_adapters(s, force_fixtures=True), session)


def seed_extended(path: str | None = None) -> int:
    """Production seed: fetch real SEC XBRL + YFinance data for top-10 S&P 500.
    SEC companyfacts are cached for ~1 year (annual 10-K filing cadence).
    Scores for Graham, Buffett, Munger, and Earnings Quality are computed here
    so they are ready to display the moment a user selects a stock, before the
    LLM promoter analysis has run."""
    from app.adapters.protocols import Constituent

    class _Top10UniverseClient:
        def fetch_constituents(self) -> list[Constituent]:
            return [Constituent(ticker=t, name=n, sector=s) for t, n, s in _TOP10]

    s = get_settings()
    migrate(path)
    # Real SEC + market adapters; universe hardcoded so startup never depends on
    # iShares network fetch. resolve_cik is now fault-tolerant (returns None on
    # EDGAR unavailability) so a single company failure won't abort the batch.
    a = build_adapters(s, force_fixtures=False)
    a.universe = _Top10UniverseClient()
    with session_scope(path) as session:
        return run_batch(a, session)


def main() -> None:  # pragma: no cover - CLI entry
    from app.core.logging import configure_logging, get_logger

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    n = seed_extended()
    get_logger("seed").info("seeded", companies=n)


if __name__ == "__main__":  # pragma: no cover
    main()
