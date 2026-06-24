"""Gate zero (decision #27): pin the live-analysis SSE contract.

This characterises the wire shape the Streamlit UI depends on, asserting INVARIANTS
(event vocabulary, per-event keys, ordering, terminal/short-circuit rules) rather than
an exact frame dump. Asserting invariants - not counts - is what lets a future engine
that emits extra stage/thought frames (the LangGraph agentic loop) satisfy the same
contract. Both engines are exercised here so the seam cannot drift under either.

Fully offline: deterministic fixture adapters + a temp DB."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from app.pipeline.sse import parse_sse

# The complete event vocabulary the UI knows how to render.
ALLOWED_EVENTS = {"stage", "thought", "citation", "scores", "done", "error"}

# Keys each event MUST carry for the consumers to work.
REQUIRED_KEYS: dict[str, set[str]] = {
    "stage": {"stage", "message"},
    "thought": {"text"},
    "citation": {"title", "url", "domain"},
    "scores": {
        "ticker",
        "narrative",
        "composite_narrative",
        "promoter",
        "composite_pct",
        "scores",
    },
    "done": {"ticker"},
    "error": {"message"},
}

# A live-engine stream factory: (adapters, ticker) -> Iterator[str of SSE frames].
StreamFactory = Callable[[Any, str], Iterator[str]]


def _linear(adapters: Any, ticker: str) -> Iterator[str]:
    from app.pipeline.analyze import analyze_stream

    return analyze_stream(adapters, ticker)


def _langgraph(adapters: Any, ticker: str) -> Iterator[str]:
    from app.pipeline.graph import stream_langgraph

    return stream_langgraph(adapters, ticker)


# Both engines must satisfy the SAME assertions - that is the whole point of the seam.
ENGINES: list[tuple[str, StreamFactory]] = [("linear", _linear), ("langgraph", _langgraph)]


def _collect(factory: StreamFactory, adapters: Any, ticker: str) -> list[tuple[str, dict]]:
    return list(parse_sse(factory(adapters, ticker)))


def _assert_vocabulary_and_keys(events: list[tuple[str, dict]]) -> None:
    for name, data in events:
        assert name in ALLOWED_EVENTS, f"unknown event '{name}'"
        missing = REQUIRED_KEYS[name] - data.keys()
        assert not missing, f"event '{name}' missing keys {missing}"


@pytest.mark.parametrize("engine_name,factory", ENGINES)
def test_successful_run_contract(engine_name, factory, fixture_adapters, seeded) -> None:
    events = _collect(factory, fixture_adapters, "AAPL")
    names = [n for n, _ in events]

    _assert_vocabulary_and_keys(events)
    assert "error" not in names, f"[{engine_name}] unexpected error frame"

    # Exactly one terminal handshake, in order: scores then done, done last.
    assert names.count("scores") == 1, f"[{engine_name}] expected one scores frame"
    assert names.count("done") == 1, f"[{engine_name}] expected one done frame"
    assert names.index("scores") < names.index("done"), f"[{engine_name}] scores must precede done"
    assert names[-1] == "done", f"[{engine_name}] done must be terminal"

    # Every stage frame names a non-empty stage; the run starts by resolving.
    stages = [d["stage"] for n, d in events if n == "stage"]
    assert all(stages), f"[{engine_name}] empty stage name"
    assert stages[0] == "resolving", f"[{engine_name}] first stage should be 'resolving'"

    # The terminal scores frame carries the analysed ticker.
    scores_data = next(d for n, d in events if n == "scores")
    assert scores_data["ticker"] == "AAPL"


@pytest.mark.parametrize("engine_name,factory", ENGINES)
def test_unresolvable_ticker_short_circuits(engine_name, factory, fixture_adapters, seeded) -> None:
    events = _collect(factory, fixture_adapters, "ZZZZ")
    names = [n for n, _ in events]

    _assert_vocabulary_and_keys(events)
    assert "error" in names, f"[{engine_name}] expected an error frame for an unresolvable ticker"
    # Error short-circuits: no terminal handshake follows.
    err_idx = names.index("error")
    assert "scores" not in names, f"[{engine_name}] no scores after error"
    assert "done" not in names[err_idx:], f"[{engine_name}] no done after error"
