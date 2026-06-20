"""FastAPI app (Q4): reads stored scores, recomputes on demand from stored inputs.
Thin shell over the pure WeightedScorer; no network/LLM in the recalc path."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from app.core.clients import build_adapters
from app.core.config import get_settings
from app.core.logging import get_logger
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
from app.pipeline.analyze import analyze_stream
from app.pipeline.market_hours import is_market_open
from app.transform.weighted_scorer import composite_pct, score_all

log = get_logger("api")
app = FastAPI(title="StockForensics API", version="0.1.0")


class _APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path.startswith("/api/"):
            s = get_settings()
            if s.api_key:
                key = request.headers.get("X-Api-Key") or request.query_params.get("api_key")
                if key != s.api_key:
                    return JSONResponse({"detail": "invalid or missing API key"}, status_code=403)
        return await call_next(request)


app.add_middleware(_APIKeyMiddleware)


class RecalcRequest(BaseModel):
    ticker: str
    # {dimension: {criterion_key: weight | null(disable)}}
    weights: dict[str, dict[str, float | None]] = {}


PROMOTER_PLACEHOLDER = "Select to calculate"


def _summary(c: CompanyScore) -> dict[str, Any]:
    # Leaderboard composite is the 4-dim deterministic one (Q22). Promoter is shown
    # only if a live run produced it (Q21), else the placeholder.
    scores = {
        k: {
            "score": v["score"],
            "max_score": v["max_score"],
            "normalized_pct": v["normalized_pct"],
            "confidence": v["confidence"],
        }
        for k, v in c.scores.items()
        if k in ("graham", "buffett", "munger", "earnings_quality")
    }
    promoter = (
        {"normalized_pct": c.scores["promoter_integrity"]["normalized_pct"], "live": True}
        if c.promoter_live and "promoter_integrity" in c.scores
        else {"placeholder": PROMOTER_PLACEHOLDER, "live": False}
    )
    analyzed_at = (
        c.run_date.replace(tzinfo=UTC).isoformat() if c.promoter_live and c.run_date else None
    )
    return {
        "ticker": c.ticker,
        "name": c.name,
        "sector": c.sector,
        "market_cap": c.market_cap,
        "composite_pct": c.composite_pct,  # 4-dim
        "scores": scores,
        "promoter": promoter,
        "analyzed_at": analyzed_at,
    }


def _detail(c: CompanyScore) -> dict[str, Any]:
    # Detail view shows the FULL 5-dim composite (incl. Promoter) when it's live (Q22).
    avail = [v["normalized_pct"] for v in c.scores.values() if v["max_score"] > 0]
    full = round(sum(avail) / len(avail), 1) if avail else 0.0
    return {
        "ticker": c.ticker,
        "name": c.name,
        "sector": c.sector,
        "market_cap": c.market_cap,
        "composite_pct_4dim": c.composite_pct,
        "composite_pct_full": full,
        "promoter_live": c.promoter_live,
        "scores": c.scores,
        "narrative": c.narrative,
        "promoter_findings": c.promoter_findings,
        "citations": c.citations or [],
    }


def _check_dimension(dimension: str) -> None:
    if dimension not in DIMENSION_KEYS:
        raise HTTPException(404, f"unknown dimension '{dimension}'")


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    with session_scope() as sess:
        last = sess.execute(select(func.max(CompanyScore.run_date))).scalar()
        count = sess.execute(select(func.count(CompanyScore.id))).scalar()
    return {
        "status": "ok",
        "sqlite": s.sqlite_path,
        "companies": count,
        "last_run": last.isoformat() if last else None,
        "keys_present": {
            "gemini": s.has("gemini_api_key"),
            "pinecone": s.has("pinecone_api_key"),
        },
    }


@app.get("/api/companies")
def companies() -> list[dict[str, Any]]:
    with session_scope() as sess:
        return [_summary(c) for c in list_companies(sess)]


@app.get("/api/companies/{ticker}")
def company(ticker: str) -> dict[str, Any]:
    with session_scope() as sess:
        c = get_company(sess, ticker)
        if c is None:
            raise HTTPException(404, f"company '{ticker}' not found")
        return _detail(c)


@app.get("/api/analysis/rankings/{dimension}")
def analysis_rankings(dimension: str) -> list[dict[str, Any]]:
    _check_dimension(dimension)
    with session_scope() as sess:
        return rankings(sess, dimension)


@app.get("/api/analysis/distribution/{dimension}")
def analysis_distribution(dimension: str) -> dict[str, Any]:
    _check_dimension(dimension)
    with session_scope() as sess:
        vals = distribution(sess, dimension)
    return {"dimension": dimension, "values": vals, "count": len(vals)}


@app.post("/api/score/recalculate")
def recalculate(req: RecalcRequest) -> dict[str, Any]:
    with session_scope() as sess:
        c = get_company(sess, req.ticker)
        if c is None:
            raise HTTPException(404, f"company '{req.ticker}' not found")
        cd = inputs_to_financials(c.inputs)
    dims = score_all(cd, req.weights or None)
    return {
        "ticker": req.ticker.upper(),
        "recalculated": {k: v.to_dict() for k, v in dims.items()},
        "composite_pct": round(composite_pct(dims), 1),
    }


def _run_batch_task() -> None:  # pragma: no cover - exercised via live run
    from app.core.clients import build_adapters
    from app.pipeline.runner import run_batch

    try:
        with session_scope() as sess:
            run_batch(build_adapters(get_settings()), sess)
    except Exception as e:
        log.error("batch_failed", error=str(e))


@app.post("/api/analysis/run")
def analysis_run(bg: BackgroundTasks) -> dict[str, str]:
    bg.add_task(_run_batch_task)
    return {"status": "started"}


_ANALYSIS_TTL_S = 14400  # 4 hours  # 1 hour


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def _cached_analysis_stream(c: CompanyScore, age_s: float) -> Iterator[str]:
    from app.pipeline.analyze import COMPLETED_STAGES

    age_min = int(age_s // 60)
    yield _sse({"type": "cached", "age_minutes": age_min})
    for st in c.thinking or COMPLETED_STAGES:
        yield _sse(
            {"type": "stage", "stage": st.get("stage", ""), "message": st.get("message", "")}
        )
    for cite in c.citations or []:
        yield _sse(
            {
                "type": "citation",
                "title": cite.get("title", ""),
                "url": cite.get("url", ""),
                "domain": cite.get("domain", ""),
            }
        )
    avail = [v["normalized_pct"] for v in c.scores.values() if v.get("max_score", 0) > 0]
    full_composite = round(sum(avail) / len(avail), 1) if avail else 0.0
    yield _sse(
        {
            "type": "scores",
            "ticker": c.ticker,
            "narrative": c.narrative or "",
            "promoter": c.scores.get("promoter_integrity", {}),
            "composite_pct": full_composite,
            "scores": c.scores,
        }
    )
    yield _sse({"type": "done", "ticker": c.ticker})


@app.get("/api/analyze/{ticker}/stream")
def analyze_stream_endpoint(ticker: str) -> StreamingResponse:
    """Lazy, live, streamed AI analysis of one selected stock (Q15, Q16).
    Server-Sent Events: stage / token / citation / scores / done.
    Returns cached result immediately if a live analysis ran within the last hour."""
    tk = ticker.upper()
    with session_scope() as sess:
        c = get_company(sess, tk)
        if c and c.promoter_live and c.run_date:
            run_dt = c.run_date if c.run_date.tzinfo else c.run_date.replace(tzinfo=UTC)
            age_s = (datetime.now(UTC) - run_dt).total_seconds()
            if age_s < _ANALYSIS_TTL_S:
                return StreamingResponse(
                    _cached_analysis_stream(c, age_s),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )
    adapters = build_adapters(get_settings())
    gen = analyze_stream(adapters, ticker)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/market/{ticker}")
def market_quote(ticker: str) -> dict[str, Any]:
    """Live market poll for the detail view (Q5). Frontend calls this every
    POLL_INTERVAL_S, up to POLL_MAX, only while the market is open. Refreshes
    valuation inputs only; never the AI."""
    s = get_settings()
    if not is_market_open():
        return {
            "ticker": ticker.upper(),
            "market_open": False,
            "poll_interval_s": s.poll_interval_s,
            "poll_max": s.poll_max,
        }
    adapters = build_adapters(s)
    md = adapters.market.get_market_data(ticker.upper())
    with session_scope() as sess:
        c = get_company(sess, ticker)
        cd = inputs_to_financials(c.inputs) if c else None
    valuation = {}
    if cd is not None:
        cd.pe, cd.pb, cd.market_cap = md.pe, md.pb, md.market_cap
        graham = score_all(cd)["graham"].to_dict()
        valuation = {"graham": graham}
    return {
        "ticker": ticker.upper(),
        "market_open": True,
        "poll_interval_s": s.poll_interval_s,
        "poll_max": s.poll_max,
        "market": {"price": md.price, "pe": md.pe, "pb": md.pb, "market_cap": md.market_cap},
        "recomputed": valuation,
    }


def _mount_spa() -> None:
    """Serve the built React SPA (single backend, Q14). Mounted LAST so all API
    routes take precedence; no-op when the frontend hasn't been built."""
    import os

    from fastapi.staticfiles import StaticFiles

    dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "dist")
    )
    if os.path.isdir(dist):
        app.mount("/", StaticFiles(directory=dist, html=True), name="spa")


_mount_spa()
