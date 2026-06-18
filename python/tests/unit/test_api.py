"""API tests via FastAPI TestClient over a seeded temp DB (offline)."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["companies"] == 2
    assert set(body["keys_present"]) == {"gemini", "pinecone"}


def test_companies_list_4dim_and_promoter_placeholder(client):
    r = client.get("/api/companies")
    assert r.status_code == 200
    rows = r.json()
    assert {row["ticker"] for row in rows} == {"AAPL", "MSFT"}
    row = rows[0]
    # leaderboard exposes only the 4 deterministic dims
    assert set(row["scores"]) == {"graham", "buffett", "munger", "earnings_quality"}
    # promoter not live yet -> placeholder
    assert row["promoter"]["live"] is False
    assert row["promoter"]["placeholder"] == "Select to calculate"


def test_company_detail(client):
    r = client.get("/api/companies/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["promoter_live"] is False
    assert "composite_pct_4dim" in body and "composite_pct_full" in body
    assert "promoter_integrity" in body["scores"]


def test_company_404(client):
    assert client.get("/api/companies/ZZZZ").status_code == 404


def test_rankings_and_bad_dimension(client):
    r = client.get("/api/analysis/rankings/graham")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["normalized_pct"] >= data[-1]["normalized_pct"]
    assert client.get("/api/analysis/rankings/nonsense").status_code == 404


def test_distribution(client):
    r = client.get("/api/analysis/distribution/buffett")
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_recalculate(client):
    r = client.post(
        "/api/score/recalculate",
        json={"ticker": "AAPL", "weights": {"graham": {"dividend_paid_5yr": None}}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert "graham" in body["recalculated"]


def test_recalculate_404(client):
    r = client.post("/api/score/recalculate", json={"ticker": "ZZZZ", "weights": {}})
    assert r.status_code == 404


def test_market_quote_has_poll_config(client):
    r = client.get("/api/market/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["poll_interval_s"] == 10 and body["poll_max"] == 60
    assert "market_open" in body


def test_analyze_stream_endpoint(client):
    r = client.get("/api/analyze/AAPL/stream")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in r.text
