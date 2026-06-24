"""LangGraph agentic engine: gap assessment (rule-#10-safe) + loop control flow.

All offline via fixtures. The contract/wire-shape is covered in test_sse_contract.py;
here we assert the agentic behaviour itself - what makes the loop loop."""

from __future__ import annotations

from typing import Any

from app.agent.research import assess_gaps
from app.pipeline.graph import stream_langgraph
from app.pipeline.sse import parse_sse


def _findings(*items: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["criterion"]: f for f in items}


_SUFFICIENT = (
    {"criterion": "ceo_tenure", "value": 10, "finding": "CEO since 2015"},
    {"criterion": "public_co_experience", "value": True, "finding": "prior public roles"},
    {"criterion": "sec_enforcement", "severity": "none", "finding": "none found"},
    {"criterion": "criminal_record", "severity": "none", "finding": "none found"},
    {"criterion": "related_party", "severity": "high", "finding": "big deal", "source_urls": ["u"]},
)


def test_assess_gaps_all_sufficient() -> None:
    assert assess_gaps(_findings(*_SUFFICIENT)) == []


def test_assess_gaps_missing_criteria_are_gaps() -> None:
    # Empty evidence => every criterion is a gap.
    assert len(assess_gaps({})) == 5


def test_assess_gaps_flags_unsourced_risk() -> None:
    # A non-"none" severity claim without a source URL is thin -> a gap.
    findings = _findings(
        *_SUFFICIENT[:4],
        {"criterion": "related_party", "severity": "low", "finding": "item", "source_urls": []},
    )
    assert assess_gaps(findings) == ["related_party"]


def test_assess_gaps_ceo_tenure_needs_number_not_bool() -> None:
    findings = _findings(
        {"criterion": "ceo_tenure", "value": True, "finding": "yes"},  # bool, not a tenure
        *_SUFFICIENT[1:],
    )
    assert "ceo_tenure" in assess_gaps(findings)


def _reasoning_passes(adapters: Any, ticker: str) -> int:
    return sum(
        1
        for n, d in parse_sse(stream_langgraph(adapters, ticker))
        if n == "stage" and d["stage"] == "reasoning"
    )


def test_loop_stops_early_when_evidence_sufficient(fixture_adapters, seeded) -> None:
    # MSFT fixture findings are all sufficient -> a single research pass, no re-research.
    assert _reasoning_passes(fixture_adapters, "MSFT") == 1


def test_loop_runs_to_max_iters_when_thin(fixture_adapters, seeded, monkeypatch) -> None:
    # AAPL's related_party fixture is unsourced, so the loop keeps chasing it to the cap.
    monkeypatch.setenv("AGENT_MAX_ITERS", "2")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert _reasoning_passes(fixture_adapters, "AAPL") == 2


def test_unresolvable_ticker_routes_to_error(fixture_adapters, seeded) -> None:
    names = [n for n, _ in parse_sse(stream_langgraph(fixture_adapters, "ZZZZ"))]
    assert names[-1] == "error"
    assert "scores" not in names
    assert "done" not in names
