"""LangGraph agentic live-analysis engine (decisions #23-28).

The whole live path is a compiled StateGraph whose cyclic core is a governance research
loop: an initial grounded pass over the 5 LLM-EVIDENCE criteria, then CODE (`assess_gaps`)
flags criteria with thin evidence and the graph re-researches ONLY those, up to
`agent_max_iters` passes or until every criterion is sufficient.

It is the opt-in alternative to the linear `analyze_stream` and emits the IDENTICAL SSE
contract (decision #27) so the UI is engine-agnostic. Nodes stream frames through the
shared wire format via LangGraph's custom stream writer; adapters are injected per run
through the runnable config so the compiled graph stays stateless and reusable."""

from __future__ import annotations

import operator
from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, Any, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.adapters.protocols import VectorItem
from app.agent.contract import validate_agent_output
from app.agent.research import assess_gaps, build_targeted_prompt
from app.agent.synthesize import RETRIEVAL_QUERY, build_composite_prompt, build_prompt
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.engine import session_scope
from app.db.models import CompanyScore
from app.db.repository import save_company_score
from app.pipeline.analyze import _assemble_live, analyze_stream
from app.pipeline.sse import sse_event, stage_event
from app.rag.chunk import chunk_filings
from app.transform.weighted_scorer import composite_pct, score_all

if TYPE_CHECKING:
    from app.core.clients import Adapters

log = get_logger("graph")


# --- state ----------------------------------------------------------------------------


def _merge_findings(
    old: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Last finding per criterion wins, so a targeted re-research replaces a thin one."""
    return {**old, **new}


def _extend_unique(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accumulate citations across passes, de-duplicated by url."""
    seen = {c.get("url") for c in old}
    return old + [c for c in new if c.get("url") not in seen]


class LiveState(TypedDict, total=False):
    ticker: str
    cik: str | None
    name: str | None
    context: str
    findings: Annotated[dict[str, dict[str, Any]], _merge_findings]
    citations: Annotated[list[dict[str, Any]], _extend_unique]
    reasoning: Annotated[list[str], operator.add]
    thinking: Annotated[list[dict[str, str]], operator.add]
    narrative: str
    iteration: int
    max_iters: int
    gaps: list[str]
    error: str


def _adapters(config: RunnableConfig) -> Adapters:
    adapters: Adapters = config["configurable"]["adapters"]
    return adapters


def _emit_stage(writer: Any, sink: list[dict[str, str]], stage: str, message: str) -> None:
    """Stream a stage frame AND record it so the thinking replay can be persisted."""
    sink.append({"stage": stage, "message": message})
    writer(stage_event(stage, message))


# --- nodes ----------------------------------------------------------------------------


def resolve(state: LiveState, config: RunnableConfig) -> dict[str, Any]:
    adapters = _adapters(config)
    tk = state["ticker"]
    writer = get_stream_writer()
    sink: list[dict[str, str]] = []
    _emit_stage(writer, sink, "resolving", f"Resolving ticker {tk} to its SEC EDGAR CIK…")
    cik = adapters.sec.resolve_cik(tk)
    if not cik:
        writer(sse_event({"type": "error", "message": f"Could not resolve CIK for {tk}"}))
        return {"error": f"no cik for {tk}", "thinking": sink}
    name: str | None = None
    with session_scope() as s:
        row = s.execute(select(CompanyScore).where(CompanyScore.ticker == tk)).scalar_one_or_none()
        if row:
            name = row.name
    return {"cik": cik, "name": name, "thinking": sink}


def rag(state: LiveState, config: RunnableConfig) -> dict[str, Any]:
    adapters = _adapters(config)
    tk = state["ticker"]
    cik = cast(str, state["cik"])  # resolve routes to END when the CIK is missing
    settings = get_settings()
    writer = get_stream_writer()
    sink: list[dict[str, str]] = []
    _emit_stage(
        writer, sink, "filings", f"CIK {cik} resolved · fetching SEC filings (10-K + DEF 14A)…"
    )
    filings = adapters.sec.get_filings(cik, ("10-K", "DEF 14A"))
    chunks = chunk_filings(filings)
    _emit_stage(
        writer,
        sink,
        "chunking",
        f"Parsed {len(filings)} filing(s) into {len(chunks)} searchable text chunks",
    )
    context = ""
    if chunks:
        _emit_stage(
            writer,
            sink,
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
        _emit_stage(
            writer,
            sink,
            "retrieving",
            f"Retrieved the {len(matches)} filing passages most relevant to governance",
        )
    return {"context": context, "thinking": sink}


def research(state: LiveState, config: RunnableConfig) -> dict[str, Any]:
    adapters = _adapters(config)
    tk = state["ticker"]
    iteration = state.get("iteration", 0)
    context = state.get("context", "")
    name = state.get("name")
    settings = get_settings()
    writer = get_stream_writer()
    sink: list[dict[str, str]] = []

    if iteration == 0:
        _emit_stage(
            writer,
            sink,
            "reasoning",
            f"Querying {settings.gemini_model} with live Google Search grounding for "
            "governance + financial evidence…",
        )
        prompt = build_prompt(tk, context, name=name)
    else:
        gaps = state.get("gaps", [])
        _emit_stage(
            writer,
            sink,
            "reasoning",
            f"Re-researching (pass {iteration + 1}): chasing thin evidence for {', '.join(gaps)}…",
        )
        prompt = build_targeted_prompt(tk, context, gaps, name=name)

    reasoning_parts: list[str] = []
    raw: dict[str, Any] = {}
    for kind, payload in adapters.llm.generate_json_streaming(prompt, grounded=True):
        if kind == "thought":
            reasoning_parts.append(payload)
            writer(sse_event({"type": "thought", "text": payload}))
        else:
            raw = payload
    contract = validate_agent_output(raw)
    new_findings = {f["criterion"]: f for f in contract["promoter_findings"]}

    update: dict[str, Any] = {
        "findings": new_findings,
        "citations": raw.get("citations", []),
        "reasoning": reasoning_parts,
        "thinking": sink,
        "iteration": iteration + 1,
    }
    if iteration == 0:  # the first pass owns the canonical narrative
        update["narrative"] = contract["narrative"]
    return update


def assess(state: LiveState, config: RunnableConfig) -> dict[str, Any]:
    findings = state.get("findings", {})
    gaps = assess_gaps(findings)
    writer = get_stream_writer()
    sink: list[dict[str, str]] = []
    n_find, n_cite = len(findings), len(state.get("citations", []))
    msg = f"Model returned {n_find} governance finding(s) and {n_cite} live web source(s)"
    if gaps and state.get("iteration", 0) < state.get("max_iters", 3):
        msg += f" · {len(gaps)} criterion(s) still thin, researching further"
    _emit_stage(writer, sink, "evidence", msg)
    return {"gaps": gaps, "thinking": sink}


def score(state: LiveState, config: RunnableConfig) -> dict[str, Any]:
    adapters = _adapters(config)
    tk = state["ticker"]
    narrative = state.get("narrative", "")
    citations = state.get("citations", [])
    writer = get_stream_writer()
    sink: list[dict[str, str]] = []

    for c in citations:
        writer(
            sse_event(
                {
                    "type": "citation",
                    "title": c.get("title", ""),
                    "url": c.get("url", ""),
                    "domain": c.get("domain", ""),
                }
            )
        )

    _emit_stage(
        writer,
        sink,
        "scoring",
        "Thresholding the evidence against the deterministic rules + scoring…",
    )
    findings = list(state.get("findings", {}).values())
    with session_scope() as session:
        cd, cik, name = _assemble_live(adapters, session, tk, findings)
        dims = score_all(cd)
        promoter = dims["promoter_integrity"].to_dict()
        full_composite = round(composite_pct(dims), 1)
        n_dims = sum(1 for d in dims.values() if d.max_score > 0)
        _emit_stage(
            writer,
            sink,
            "scored",
            f"Promoter Integrity {promoter['score']:.1f}/{promoter['max_score']:.1f} "
            f"({promoter['normalized_pct']:.0f}%) · composite {full_composite:.0f}% "
            f"across {n_dims} scored dimensions",
        )
        composite_narrative = adapters.llm.generate_text(
            build_composite_prompt(tk, full_composite, dims)
        )
        _emit_stage(
            writer, sink, "rationale", f"Explained the {full_composite:.0f}% composite verdict"
        )
        save_company_score(
            session,
            cd,
            dims,
            name=name,
            cik=cik,
            narrative=narrative,
            composite_narrative=composite_narrative,
            reasoning="".join(state.get("reasoning", [])),
            promoter_live=True,
            citations=citations,
            thinking=state.get("thinking", []) + sink,
        )

    writer(
        sse_event(
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
    )
    writer(sse_event({"type": "done", "ticker": tk}))
    return {"thinking": sink}


# --- wiring ---------------------------------------------------------------------------


def _route_after_resolve(state: LiveState) -> str:
    return END if state.get("error") else "rag"


def _route_after_assess(state: LiveState) -> str:
    """Loop back to research while criteria are thin and the iteration budget remains."""
    if state.get("gaps") and state.get("iteration", 0) < state.get("max_iters", 3):
        return "research"
    return "score"


def build_live_graph() -> Any:
    g = StateGraph(LiveState)
    g.add_node("resolve", resolve)
    g.add_node("rag", rag)
    g.add_node("research", research)
    g.add_node("assess", assess)
    g.add_node("score", score)
    g.add_edge(START, "resolve")
    g.add_conditional_edges("resolve", _route_after_resolve, {"rag": "rag", END: END})
    g.add_edge("rag", "research")
    g.add_edge("research", "assess")
    g.add_conditional_edges(
        "assess", _route_after_assess, {"research": "research", "score": "score"}
    )
    g.add_edge("score", END)
    return g.compile()


# Compiled once; stateless. Adapters + iteration budget are passed per run.
LIVE_GRAPH = build_live_graph()


def stream_langgraph(adapters: Adapters, ticker: str) -> Iterator[str]:
    """Drive the agentic graph, relaying its SSE frames - same contract as analyze_stream."""
    tk = ticker.upper()
    settings = get_settings()
    initial: LiveState = {
        "ticker": tk,
        "iteration": 0,
        "max_iters": settings.agent_max_iters,
        "findings": {},
        "citations": [],
        "reasoning": [],
        "thinking": [],
    }
    config: RunnableConfig = {"configurable": {"adapters": adapters}}
    yield from LIVE_GRAPH.stream(initial, config=config, stream_mode="custom")
    log.info("langgraph_analyze_complete", ticker=tk)


def run_live_analysis(adapters: Adapters, ticker: str, *, engine: str = "linear") -> Iterator[str]:
    """Dispatch live analysis to the chosen engine. Both yield the identical SSE contract."""
    if engine == "langgraph":
        return stream_langgraph(adapters, ticker)
    return analyze_stream(adapters, ticker)
