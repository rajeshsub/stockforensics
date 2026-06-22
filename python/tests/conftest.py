"""Shared fixtures. Everything offline + deterministic (Q6)."""

from __future__ import annotations

import pytest

from app.adapters.fixtures import (
    FixtureMarketClient,
    FixtureSecClient,
    promoter_findings_of,
    sector_of,
)
from app.transform.models import CompanyFinancials
from app.transform.xbrl_map import build_company_financials


def _build(ticker: str, **overrides) -> CompanyFinancials:
    sec, mkt = FixtureSecClient(), FixtureMarketClient()
    cik = sec.resolve_cik(ticker)
    assert cik is not None
    cd = build_company_financials(
        ticker,
        sec.get_company_facts(cik),
        mkt.get_market_data(ticker),
        sec.get_insider_summary(cik),
        sector=sector_of(ticker),
        sector_pe_percentile=0.3,
        sector_pb_percentile=0.3,
        sector_peer_count=8,
        promoter_findings=promoter_findings_of(ticker),
        auditor_years=8,
    )
    for k, v in overrides.items():
        setattr(cd, k, v)
    return cd


@pytest.fixture
def aapl() -> CompanyFinancials:
    return _build("AAPL")


@pytest.fixture
def msft() -> CompanyFinancials:
    return _build("MSFT")


@pytest.fixture
def build():
    return _build


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh on-disk SQLite pointed at by settings; caches cleared around it."""
    from app.core.config import get_settings
    from app.db.engine import get_engine
    from app.db.migrate import migrate

    db = str(tmp_path / "t.db")
    monkeypatch.setenv("SQLITE_PATH", db)
    monkeypatch.setenv("API_KEY", "")  # disable gateway auth in tests
    get_settings.cache_clear()
    get_engine.cache_clear()
    migrate()
    yield db
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def seeded(temp_db):
    """temp_db populated with the deterministic fixture batch."""
    from app.db.seed import seed

    seed()
    return temp_db


@pytest.fixture
def fixture_adapters():
    from app.core.clients import build_adapters

    return build_adapters(force_fixtures=True)
