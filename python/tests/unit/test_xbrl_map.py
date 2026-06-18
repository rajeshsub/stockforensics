"""Unit tests for XBRL companyfacts -> CompanyFinancials assembly."""

from __future__ import annotations

from app.adapters.fixtures import FixtureMarketClient, FixtureSecClient
from app.transform.xbrl_map import _concept_series, build_company_financials


def test_concept_series_picks_annual_10k():
    sec = FixtureSecClient()
    facts = sec.get_company_facts("0000320193")
    s = _concept_series(facts, ["NetIncomeLoss"])
    assert len(s) == 5
    assert s[2025] == 86  # newest year


def test_concept_series_missing_returns_empty():
    assert _concept_series({"facts": {"us-gaap": {}}}, ["Nope"]) == {}


def test_build_company_financials_aapl():
    sec, mkt = FixtureSecClient(), FixtureMarketClient()
    cd = build_company_financials(
        "AAPL",
        sec.get_company_facts("0000320193"),
        mkt.get_market_data("AAPL"),
        sec.get_insider_summary("0000320193"),
        sector="Technology",
        auditor_years=8,
    )
    assert cd.ticker == "AAPL"
    assert len(cd.eps) == 5
    assert len(cd.roe) == 5
    assert len(cd.gross_margin) == 5
    # current ratio computed from facts: 150 / 70
    assert abs(cd.current_ratio - 150 / 70) < 1e-6
    # debt/equity latest: 85 / 360
    assert abs(cd.debt_to_equity - 85 / 360) < 1e-6
    # special items absent -> empty (will NA downstream)
    assert cd.special_items == []
    # capex stored as positive
    assert all(x >= 0 for x in cd.capex)


def test_build_handles_empty_facts():
    cd = build_company_financials(
        "ZZZ",
        {"facts": {"us-gaap": {}}},
        FixtureMarketClient().get_market_data("ZZZ"),
        FixtureSecClient().get_insider_summary("x"),
    )
    assert cd.eps == []
    assert cd.debt_to_equity is None
    assert cd.current_ratio is None
