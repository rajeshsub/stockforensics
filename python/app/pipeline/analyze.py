"""On-selection live analysis (Q4=C, Q16). Refreshes fast-moving market data live,
reuses (re-fetches) SEC fundamentals, runs the AI, streams the thinking process,
finalises the full 5-dimension score incl. live Promoter, and persists it so the
list can show the cached value (Q21). Adapters injected -> offline (fixtures) or live."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.protocols import InsiderSummary, VectorItem
from app.agent.contract import validate_agent_output
from app.agent.synthesize import (
    RETRIEVAL_QUERY,
    build_composite_prompt,
    build_prompt,
    retrieve_context,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.engine import session_scope
from app.db.models import CompanyScore
from app.db.repository import save_company_score
from app.rag.chunk import chunk_filings
from app.transform.models import CompanyFinancials
from app.transform.weighted_scorer import composite_pct, score_all
from app.transform.xbrl_map import build_company_financials

if TYPE_CHECKING:
    from app.core.clients import Adapters

log = get_logger("analyze")

# Representative completed pipeline, used by the non-streaming path and as the
# cached-view fallback so the thinking stream always has stages to show (Q16).
COMPLETED_STAGES: list[dict[str, str]] = [
    {"stage": "resolving", "message": "Resolved company + SEC EDGAR CIK"},
    {"stage": "filings", "message": "Fetched SEC filings (10-K + DEF 14A)"},
    {"stage": "chunking", "message": "Parsed filings into text chunks"},
    {"stage": "embedding", "message": "Embedded chunks for semantic retrieval"},
    {"stage": "retrieving", "message": "Retrieved the most relevant filing passages"},
    {"stage": "reasoning", "message": "Queried the model with live Google Search grounding"},
    {"stage": "evidence", "message": "Extracted governance findings + web citations"},
    {"stage": "scoring", "message": "Thresholded evidence against the rules + scored"},
]


def _attach_sector_context_from_peers(session: Session, cd: CompanyFinancials) -> None:
    """Compute sector-relative P/E & P/B percentiles using the batch's stored peers."""
    rows = (
        session.execute(select(CompanyScore).where(CompanyScore.sector == cd.sector))
        .scalars()
        .all()
    )
    pes = [float(r.inputs["pe"]) for r in rows if r.inputs.get("pe") is not None]
    pbs = [float(r.inputs["pb"]) for r in rows if r.inputs.get("pb") is not None]
    cd.sector_peer_count = max(len(rows), 1)
    if cd.pe is not None and len(pes) >= 2:
        cd.sector_pe_percentile = sum(1 for p in pes if p < cd.pe) / (len(pes) - 1)
    if cd.pb is not None and len(pbs) >= 2:
        cd.sector_pb_percentile = sum(1 for p in pbs if p < cd.pb) / (len(pbs) - 1)


def _assemble_live(adapters: Adapters, session: Session, ticker: str, findings: list) -> tuple:
    """Build a CompanyFinancials with fresh market + cached fundamentals + live findings."""
    cik = adapters.sec.resolve_cik(ticker)
    facts = adapters.sec.get_company_facts(cik) if cik else {"facts": {"us-gaap": {}}}
    market = adapters.market.get_market_data(ticker)  # FRESH (Q4=C)
    insider = adapters.sec.get_insider_summary(cik) if cik else InsiderSummary()
    prior = session.execute(
        select(CompanyScore).where(CompanyScore.ticker == ticker.upper())
    ).scalar_one_or_none()
    sector = prior.sector if prior else None
    name = prior.name if prior else None
    cd = build_company_financials(
        ticker.upper(), facts, market, insider, sector=sector, promoter_findings=findings
    )
    _attach_sector_context_from_peers(session, cd)
    return cd, cik, name


def analyze_company(adapters: Adapters, session: Session, ticker: str) -> dict[str, Any]:
    """Non-streaming live analysis: run AI, score, persist, return the full result."""
    cik = adapters.sec.resolve_cik(ticker)
    context = retrieve_context(adapters, ticker.upper(), cik) if cik else ""
    raw = adapters.llm.generate_json(build_prompt(ticker.upper(), context), grounded=True)
    contract = validate_agent_output(raw)

    cd, cik, name = _assemble_live(adapters, session, ticker, contract["promoter_findings"])
    dims = score_all(cd)
    full_composite = round(composite_pct(dims), 1)
    composite_narrative = adapters.llm.generate_text(
        build_composite_prompt(ticker.upper(), full_composite, dims)
    )
    save_company_score(
        session,
        cd,
        dims,
        name=name,
        cik=cik,
        narrative=contract["narrative"],
        composite_narrative=composite_narrative,
        promoter_live=True,
        citations=raw.get("citations", []),
        thinking=COMPLETED_STAGES,
    )
    return {
        "ticker": ticker.upper(),
        "narrative": contract["narrative"],
        "composite_narrative": composite_narrative,
        "citations": raw.get("citations", []),
        "scores": {k: v.to_dict() for k, v in dims.items()},
        "composite_pct": round(composite_pct(dims), 1),
        "promoter": dims["promoter_integrity"].to_dict(),
    }


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def _stage(stage: str, message: str) -> str:
    return _sse({"type": "stage", "stage": stage, "message": message})


def analyze_stream(adapters: Adapters, ticker: str) -> Iterator[str]:
    """Stream the AI's thinking as SSE: stage events + narrative tokens + citations,
    then the final live scores. Persists the result at the end (Q16, Q21)."""
    tk = ticker.upper()
    settings = get_settings()
    # record each stage so cached/return views can replay the thinking stream (Q16)
    thinking: list[dict[str, str]] = []

    def stage(s: str, message: str) -> str:
        thinking.append({"stage": s, "message": message})
        return _stage(s, message)

    yield stage("resolving", f"Resolving ticker {tk} to its SEC EDGAR CIK…")
    cik = adapters.sec.resolve_cik(tk)
    if not cik:
        yield _sse({"type": "error", "message": f"Could not resolve CIK for {tk}"})
        return

    yield stage("filings", f"CIK {cik} resolved · fetching SEC filings (10-K + DEF 14A)…")
    filings = adapters.sec.get_filings(cik, ("10-K", "DEF 14A"))
    chunks = chunk_filings(filings)
    yield stage(
        "chunking", f"Parsed {len(filings)} filing(s) into {len(chunks)} searchable text chunks"
    )

    context = ""
    if chunks:
        yield stage(
            "embedding",
            f"Embedding {len(chunks)} chunks with {settings.gemini_embed_model} for retrieval…",
        )
        vectors = adapters.llm.embed([c.text for c in chunks])
        adapters.vector.upsert(
            tk,
            [
                VectorItem(c.id, v, {"text": c.text, "form": c.form})
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )
        qvec = adapters.llm.embed([RETRIEVAL_QUERY])[0]
        matches = adapters.vector.query(tk, qvec, top_k=4)
        context = "\n".join(str(m.metadata.get("text", "")) for m in matches)
        yield stage(
            "retrieving",
            f"Retrieved the {len(matches)} filing passages most relevant to governance",
        )

    yield stage(
        "reasoning",
        f"Querying {settings.gemini_model} with live Google Search grounding for "
        "governance + financial evidence…",
    )
    prompt = build_prompt(tk, context)
    raw = adapters.llm.generate_json(prompt, grounded=True)
    contract = validate_agent_output(raw)

    n_find = len(contract["promoter_findings"])
    n_cite = len(raw.get("citations", []))
    yield stage(
        "evidence",
        f"Model returned {n_find} governance finding(s) and {n_cite} live web source(s)",
    )
    for cite in raw.get("citations", []):
        yield _sse(
            {
                "type": "citation",
                "title": cite.get("title", ""),
                "url": cite.get("url", ""),
                "domain": cite.get("domain", ""),
            }
        )

    yield stage("scoring", "Thresholding the evidence against the deterministic rules + scoring…")
    with session_scope() as session:
        cd, cik, name = _assemble_live(adapters, session, tk, contract["promoter_findings"])
        dims = score_all(cd)
        narrative = contract["narrative"]
        promoter = dims["promoter_integrity"].to_dict()
        full_composite = round(composite_pct(dims), 1)
        n_dims = sum(1 for d in dims.values() if d.max_score > 0)
        summary = stage(
            "scored",
            f"Promoter Integrity {promoter['score']:.1f}/{promoter['max_score']:.1f} "
            f"({promoter['normalized_pct']:.0f}%) · composite {full_composite:.0f}% "
            f"across {n_dims} scored dimensions",
        )
        composite_narrative = adapters.llm.generate_text(
            build_composite_prompt(tk, full_composite, dims)
        )
        rationale = stage("rationale", f"Explained the {full_composite:.0f}% composite verdict")
        save_company_score(
            session,
            cd,
            dims,
            name=name,
            cik=cik,
            narrative=narrative,
            composite_narrative=composite_narrative,
            promoter_live=True,
            citations=raw.get("citations", []),
            thinking=thinking,
        )

    yield summary
    yield rationale
    yield _sse(
        {
            "type": "scores",
            "ticker": tk,
            "narrative": narrative,
            "composite_narrative": composite_narrative,
            "promoter": promoter,
            "composite_pct": full_composite,
            "scores": {k: v.to_dict() for k, v in dims.items()},
        }
    )
    yield _sse({"type": "done", "ticker": tk})
    log.info("analyze_stream_complete", ticker=tk)
