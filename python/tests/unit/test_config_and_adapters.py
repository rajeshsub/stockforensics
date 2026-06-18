"""Unit tests for config + fixture adapters (shape/plumbing, offline)."""

from __future__ import annotations

from app.adapters.fixtures import (
    FixtureLlmClient,
    FixtureMarketClient,
    FixtureSecClient,
    FixtureUniverseClient,
    FixtureVectorClient,
)
from app.adapters.protocols import VectorItem
from app.core.config import Settings
from app.core.logging import configure_logging, get_logger


def test_settings_defaults_and_clamp():
    s = Settings(top_n=500)
    assert s.top_n_clamped == 100
    assert Settings(top_n=0).top_n_clamped == 1
    assert s.has("sec_user_agent") is True
    assert s.has("gemini_api_key") is False  # empty by default
    assert s.poll_interval_s == 10 and s.poll_max == 60


def test_logging_configures(capsys):
    configure_logging(level="INFO", json=True)
    get_logger("t").info("hello", k=1)
    out = capsys.readouterr().out
    assert "hello" in out


def test_sec_client_resolves_and_facts():
    sec = FixtureSecClient()
    assert sec.resolve_cik("AAPL") == "0000320193"
    assert sec.resolve_cik("NOPE") is None
    facts = sec.get_company_facts("0000320193")
    assert facts["entityName"] == "Apple Inc."
    assert sec.get_insider_summary("0000320193").ownership_pct == 0.83
    filings = sec.get_filings("0000320193", ("10-K", "DEF 14A"))
    assert {f.form for f in filings} == {"10-K", "DEF 14A"}


def test_market_and_universe():
    assert FixtureMarketClient().get_market_data("AAPL").pe == 12.5
    assert FixtureMarketClient().get_market_data("UNKNOWN").pe is None
    cons = FixtureUniverseClient().fetch_constituents()
    assert {c.ticker for c in cons} == {"AAPL", "MSFT"}


def test_llm_embed_json_and_stream():
    llm = FixtureLlmClient()
    v1 = llm.embed(["abc"])
    v2 = llm.embed(["abc"])
    assert v1 == v2 and len(v1[0]) == 8
    out = llm.generate_json("synthesis for AAPL", grounded=True)
    assert "narrative" in out
    assert any(f["criterion"] == "ceo_tenure" for f in out["promoter_findings"])
    assert out["citations"]
    streamed = "".join(llm.generate_stream("synthesis for AAPL"))
    assert "AAPL" in streamed


def test_vector_upsert_query_ranks():
    vc = FixtureVectorClient()
    vc.upsert(
        "AAPL",
        [
            VectorItem("a", [1, 0, 0, 0, 0, 0, 0, 0], {"chunk": "a"}),
            VectorItem("b", [0, 1, 0, 0, 0, 0, 0, 0], {"chunk": "b"}),
        ],
    )
    matches = vc.query("AAPL", [1, 0, 0, 0, 0, 0, 0, 0], top_k=1)
    assert matches[0].id == "a"
    assert vc.query("EMPTY", [1, 0, 0, 0, 0, 0, 0, 0]) == []
