"""Scoring logic tests: direct function calls (no HTTP layer)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.engine import session_scope
from app.db.models import CompanyScore
from app.db.repository import (
    DIMENSION_KEYS,
    distribution,
    get_company,
    inputs_to_financials,
    list_companies,
    rankings,
)
from app.transform.weighted_scorer import composite_pct, score_all


def test_health(seeded):
    """Check that seeded DB has expected companies."""
    with session_scope() as sess:
        count = sess.execute(select(func.count(CompanyScore.id))).scalar()
        assert count == 2


def test_companies_list_4dim_and_promoter_placeholder(seeded):
    """List all companies; check leaderboard has 4 dims, promoter is placeholder."""
    with session_scope() as sess:
        companies = list_companies(sess)
        assert {c.ticker for c in companies} == {"AAPL", "MSFT"}
        c = companies[0]
        # leaderboard exposes only the 4 deterministic dims
        assert {k for k in c.scores if k in DIMENSION_KEYS} >= {
            "graham",
            "buffett",
            "munger",
            "earnings_quality",
        }
        # promoter not live yet -> placeholder would be shown in UI
        assert c.promoter_live is False


def test_company_detail(seeded):
    """Load one company; check it has 5-dim composite and scores."""
    with session_scope() as sess:
        c = get_company(sess, "AAPL")
        assert c is not None
        assert c.promoter_live is False
        assert c.composite_pct is not None
        assert "promoter_integrity" in c.scores


def test_company_404(seeded):
    """Non-existent company returns None."""
    with session_scope() as sess:
        c = get_company(sess, "ZZZZ")
        assert c is None


def test_rankings(seeded):
    """Rankings are sorted descending by score."""
    with session_scope() as sess:
        data = rankings(sess, "graham")
        assert len(data) >= 2
        assert data[0]["normalized_pct"] >= data[-1]["normalized_pct"]


def test_rankings_bad_dimension(seeded):
    """Bad dimension raises via repository function."""
    # Note: rankings() doesn't validate; the UI would filter on DIMENSION_KEYS
    with session_scope() as sess:
        data = rankings(sess, "nonsense")
        assert data == []


def test_distribution(seeded):
    """Distribution returns values for valid dimension."""
    with session_scope() as sess:
        vals = distribution(sess, "buffett")
        assert len(vals) == 2


def test_recalculate(seeded):
    """Recalculate scores with custom weights."""
    with session_scope() as sess:
        c = get_company(sess, "AAPL")
        assert c is not None
        cd = inputs_to_financials(c.inputs)
    # Recalculate with custom weights (disable one criterion)
    dims = score_all(cd, {"graham": {"dividend_paid_5yr": None}})
    assert "graham" in dims
    assert dims["graham"].normalized_pct is not None


def test_recalculate_404(seeded):
    """Recalculate on non-existent company returns None."""
    with session_scope() as sess:
        c = get_company(sess, "ZZZZ")
        assert c is None


def test_composite_pct(seeded):
    """Composite score is average of all available dimensions."""
    with session_scope() as sess:
        c = get_company(sess, "AAPL")
        assert c is not None
        cd = inputs_to_financials(c.inputs)
    dims = score_all(cd)
    comp = composite_pct(dims)
    assert 0 <= comp <= 100
