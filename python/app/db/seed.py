"""DB seeding utilities.

seed()          - fixture-only, offline, used by tests and make bootstrap.
seed_extended() - top-10 S&P 500 via hardcoded list + fixture scoring; used by
                  the Streamlit app on first boot. No network calls, no file deps.
"""

from __future__ import annotations

from app.core.clients import build_adapters
from app.core.config import get_settings
from app.db.engine import session_scope
from app.db.migrate import migrate
from app.pipeline.runner import run_batch


def seed(path: str | None = None) -> int:
    """Fixture-only seed: AAPL + MSFT with full deterministic scores."""
    s = get_settings()
    migrate(path)
    with session_scope(path) as session:
        return run_batch(build_adapters(s, force_fixtures=True), session)


def seed_extended(path: str | None = None) -> int:
    """Production seed: top-10 S&P 500 hardcoded + fixture scoring data.
    All 10 appear in the combo box; AAPL/MSFT get full scores, others minimal."""
    from app.adapters.protocols import Constituent

    _TOP10 = [
        Constituent("AAPL", "Apple Inc", "Information Technology"),
        Constituent("MSFT", "Microsoft Corp", "Information Technology"),
        Constituent("NVDA", "NVIDIA Corp", "Information Technology"),
        Constituent("AMZN", "Amazon.com Inc", "Consumer Discretionary"),
        Constituent("GOOGL", "Alphabet Inc", "Communication Services"),
        Constituent("META", "Meta Platforms Inc", "Communication Services"),
        Constituent("TSLA", "Tesla Inc", "Consumer Discretionary"),
        Constituent("BRK.B", "Berkshire Hathaway", "Financials"),
        Constituent("AVGO", "Broadcom Inc", "Information Technology"),
        Constituent("JPM", "JPMorgan Chase & Co", "Financials"),
    ]

    class _Top10UniverseClient:
        def fetch_constituents(self) -> list[Constituent]:
            return list(_TOP10)

    s = get_settings()
    migrate(path)
    a = build_adapters(s, force_fixtures=True)
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
