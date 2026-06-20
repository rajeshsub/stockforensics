"""Per-company qualitative synthesis (Q5, Q17). RAG over SEC filings (chunk ->
embed -> Pinecone -> retrieve) for filing-grounded context, plus Gemini's built-in
google_search grounding for fresh web/news. One grounded LLM call returns the agent
contract; code (not the LLM) later thresholds the promoter findings into the score."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.adapters.protocols import VectorItem
from app.agent.contract import validate_agent_output
from app.rag.chunk import chunk_filings

if TYPE_CHECKING:
    from app.core.clients import Adapters
    from app.transform.models import ScoringDimension

RETRIEVAL_QUERY = (
    "executive integrity, CEO tenure, public-company experience, SEC enforcement "
    "actions, criminal record, related-party transactions, insider selling"
)


def retrieve_context(adapters: Adapters, ticker: str, cik: str) -> str:
    """RAG: chunk filings -> embed -> Pinecone upsert -> retrieve top-k passages."""
    filings = adapters.sec.get_filings(cik, ("10-K", "DEF 14A"))
    chunks = chunk_filings(filings)
    if not chunks:
        return ""
    vectors = adapters.llm.embed([c.text for c in chunks])
    adapters.vector.upsert(
        ticker,
        [
            VectorItem(c.id, v, {"text": c.text, "form": c.form})
            for c, v in zip(chunks, vectors, strict=True)
        ],
    )
    qvec = adapters.llm.embed([RETRIEVAL_QUERY])[0]
    matches = adapters.vector.query(ticker, qvec, top_k=4)
    return "\n".join(str(m.metadata.get("text", "")) for m in matches)


def build_prompt(ticker: str, context: str) -> str:
    return (
        f"You are an equity research assistant analysing {ticker}. Use the SEC filing "
        f"excerpts below AND a live web search (google_search) for recent news. The "
        '"narrative" is a QUALITATIVE BRIEF of what the filings and the live web turned '
        "up about the company: open with a 1-2 sentence executive summary paragraph (no "
        "heading), then 3-5 sections each introduced by a '## Heading' (e.g. "
        "## Business & Moat, ## Financial Health, ## Recent Developments, ## Risks, "
        "## Governance); keep each section to a short paragraph or a few bullet points. "
        "Do NOT mention or speculate about any composite score in the narrative - it is "
        "purely a summary of the evidence. Return "
        'STRICT JSON: {"narrative": str, "promoter_findings": [{"criterion": one of '
        "[ceo_tenure, public_co_experience, sec_enforcement, criminal_record, "
        'related_party], "value": number|boolean|null, "severity": '
        '"none|low|medium|high", "finding": str, "source_urls": [str]}], '
        '"citations": [{"title": str, "url": str}]}. Do NOT compute any financial '
        "figure or score; report only qualitative evidence; code will threshold it.\n\n"
        f"SEC FILING EXCERPTS:\n{context or '(none)'}"
    )


def _dims_digest(dims: dict[str, ScoringDimension]) -> str:
    """Compact text view of the scored dimensions + their per-criterion verdicts, so the
    model can explain the composite without re-deriving any figure itself."""
    lines: list[str] = []
    for d in dims.values():
        if d.max_score <= 0:
            continue
        crits = [
            f"{c.label} [{c.status}]: {c.reason}"
            for c in d.criteria
            if c.max_points > 0 and c.reason
        ]
        detail = ("; ".join(crits)) or "no scored criteria"
        lines.append(f"- {d.name}: {d.normalized_pct:.0f}% ({detail})")
    return "\n".join(lines) or "(no dimensions scored)"


def build_composite_prompt(
    ticker: str, composite_pct: float, dims: dict[str, ScoringDimension]
) -> str:
    """Prompt for the composite RATIONALE: the model explains, in its own words, why the
    deterministic engine landed on this overall score. No web search, no new facts - it
    reasons strictly over the dimension breakdown below."""
    return (
        f"A deterministic stock-screening engine scored {ticker} at {composite_pct:.0f}% "
        "overall, computed as the average of these scored dimensions:\n\n"
        f"{_dims_digest(dims)}\n\n"
        f"Explain, IN YOUR OWN WORDS, why {ticker} earned {composite_pct:.0f}%. Do NOT "
        "search the web or introduce any fact or number not present in the breakdown "
        "above. Output plain markdown (no JSON, no '##' headings): open with one short "
        "**bold** sentence stating the overall verdict and the single biggest driver, "
        "then 2-4 bullet points each naming a dimension and what pulled its score up or "
        "down, citing that dimension's percentage. Keep the whole thing under 110 words."
    )


def synthesize_company(adapters: Adapters, ticker: str, cik: str) -> dict[str, Any]:
    """Non-streaming synthesis (used where a stream isn't needed / in tests)."""
    context = retrieve_context(adapters, ticker, cik)
    raw = adapters.llm.generate_json(build_prompt(ticker, context), grounded=True)
    return validate_agent_output(raw)
