"""Offline tests for the batch runner, live-analyze path, RAG, agent, market-hours."""

from __future__ import annotations

from datetime import datetime

from app.agent.contract import validate_agent_output
from app.agent.synthesize import synthesize_company
from app.db.engine import session_scope
from app.db.repository import get_company, inputs_to_financials, list_companies
from app.pipeline import market_hours as mh
from app.pipeline.analyze import analyze_company, analyze_stream
from app.pipeline.runner import _attach_sector_context, run_batch
from app.rag.chunk import chunk_filings, chunk_text
from app.transform.models import CompanyFinancials


def test_run_batch_offline_deterministic(temp_db, fixture_adapters):
    with session_scope() as s:
        n = run_batch(fixture_adapters, s, top_n=100)
    assert n == 2
    with session_scope() as s:
        cos = list_companies(s)
        assert {c.ticker for c in cos} == {"AAPL", "MSFT"}
        # Batch is deterministic-only: promoter not live yet
        assert all(c.promoter_live is False for c in cos)
        # Leaderboard composite is 4-dim and ordered desc
        assert cos[0].composite_pct >= cos[-1].composite_pct


def test_attach_sector_context():
    a = CompanyFinancials(ticker="A", sector="Tech", pe=10, pb=1)
    b = CompanyFinancials(ticker="B", sector="Tech", pe=30, pb=5)
    c = CompanyFinancials(ticker="C", sector="Tech", pe=20, pb=3)
    _attach_sector_context([a, b, c])
    assert a.sector_peer_count == 3
    assert a.sector_pe_percentile == 0.0  # cheapest
    assert b.sector_pe_percentile == 1.0  # priciest


def test_agent_synthesize_and_contract(fixture_adapters):
    out = synthesize_company(fixture_adapters, "AAPL", "0000320193")
    assert out["narrative"]
    assert any(f["criterion"] == "ceo_tenure" for f in out["promoter_findings"])


def test_validate_agent_output_drops_unknown_and_coerces():
    raw = {
        "narrative": 123,  # non-str coerced
        "promoter_findings": [
            {"criterion": "sec_enforcement", "severity": "HIGH"},
            {"criterion": "not_a_real_one", "value": 1},
            "garbage",
        ],
    }
    out = validate_agent_output(raw)
    assert isinstance(out["narrative"], str)
    keys = [f["criterion"] for f in out["promoter_findings"]]
    assert keys == ["sec_enforcement"]
    assert out["promoter_findings"][0]["severity"] == "high"


def test_chunking():
    assert chunk_text("") == []
    pieces = chunk_text("word " * 300, size=120, overlap=20)
    assert len(pieces) >= 2
    chunks = chunk_filings(
        [type("F", (), {"text": "a b c d e", "form": "10-K"})()], size=2, overlap=0
    )
    assert all(c.form == "10-K" for c in chunks)


def test_analyze_company_promoter_live(temp_db, fixture_adapters):
    # need a prior row so sector/name resolve + peers exist
    with session_scope() as s:
        run_batch(fixture_adapters, s, top_n=100)
    with session_scope() as s:
        result = analyze_company(fixture_adapters, s, "AAPL")
    assert result["ticker"] == "AAPL"
    assert "promoter_integrity" in result["scores"]
    with session_scope() as s:
        c = get_company(s, "AAPL")
        assert c.promoter_live is True
        assert c.narrative


def test_analyze_stream_emits_events(seeded, fixture_adapters):
    events = list(analyze_stream(fixture_adapters, "AAPL"))
    text = "".join(events)
    for etype in ("stage", "scores", "done"):
        assert f"event: {etype}" in text
    # SSE framing
    assert text.startswith("event: stage")


def test_analyze_stream_unknown_ticker(seeded, fixture_adapters):
    events = list(analyze_stream(fixture_adapters, "ZZZZ"))
    assert any("event: error" in e for e in events)


def test_recalc_from_stored_inputs(seeded):
    with session_scope() as s:
        c = get_company(s, "AAPL")
        cd = inputs_to_financials(c.inputs)
    assert isinstance(cd, CompanyFinancials)
    assert cd.ticker == "AAPL"


def test_market_hours():
    # Sat 2026-06-20
    assert mh.is_market_open(datetime(2026, 6, 20, 15, 0)) is False
    # Juneteenth holiday 2026-06-19 (Fri)
    assert mh.is_trading_day(datetime(2026, 6, 19, 14, 0)) is False
    # A normal weekday inside the session is naive-UTC -> still computes a bool
    assert isinstance(mh.is_market_open(), bool)
