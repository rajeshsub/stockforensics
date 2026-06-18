"""Live plumbing+shape smoke tests (Q6b). Non-gating: marked `smoke`, excluded
from the default run. Assert structure/types only, never specific values. Each
skips if its required key/network is absent. Run via `make smoke`."""

from __future__ import annotations

import pytest

from app.adapters.protocols import MarketData
from app.core.config import get_settings

pytestmark = pytest.mark.smoke


def test_sec_resolve_and_facts_shape():
    from app.adapters.sec_client import HttpxSecClient

    sec = HttpxSecClient(get_settings().sec_user_agent)
    cik = sec.resolve_cik("AAPL")
    assert cik is not None and len(cik) == 10 and cik.isdigit()
    facts = sec.get_company_facts(cik)
    assert "facts" in facts


def test_sec_filings_shape():
    from app.adapters.sec_client import HttpxSecClient

    sec = HttpxSecClient(get_settings().sec_user_agent)
    cik = sec.resolve_cik("AAPL")
    assert cik is not None
    filings = sec.get_filings(cik, ("10-K",))
    if filings:  # filing availability varies; assert shape when present
        assert filings[0].form == "10-K"
        assert isinstance(filings[0].text, str)


def test_market_shape():
    from app.adapters.market_client import YFinanceMarketClient

    md = YFinanceMarketClient().get_market_data("AAPL")
    assert isinstance(md, MarketData)
    assert md.ticker == "AAPL"
    for v in (md.pe, md.pb, md.market_cap):
        assert v is None or isinstance(v, int | float)


def test_universe_snapshot_loads():
    from app.pipeline.universe import load_snapshot

    rows = load_snapshot()
    if rows:
        assert "ticker" in rows[0]


@pytest.mark.skipif(not get_settings().has("gemini_api_key"), reason="no GEMINI_API_KEY")
def test_gemini_embed_and_json_shape():
    from app.adapters.llm_client import GeminiLlmClient

    llm = GeminiLlmClient(get_settings())
    vecs = llm.embed(["hello world"])
    assert vecs and isinstance(vecs[0], list) and len(vecs[0]) > 0
    out = llm.generate_json('Return JSON {"narrative":"hi","promoter_findings":[]}.')
    assert isinstance(out, dict)


@pytest.mark.skipif(not get_settings().has("pinecone_api_key"), reason="no PINECONE_API_KEY")
def test_pinecone_upsert_query_shape():
    from app.adapters.protocols import VectorItem
    from app.adapters.vector_client import EMBED_DIM, PineconeVectorClient

    vc = PineconeVectorClient(get_settings())
    vec = [0.01] * EMBED_DIM
    vc.upsert("smoke", [VectorItem("smoke-1", vec, {"text": "x"})])
    matches = vc.query("smoke", vec, top_k=1)
    assert isinstance(matches, list)
