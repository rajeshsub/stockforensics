"""Single source of truth for the SSE wire format (decision #27).

Both live engines (linear `analyze_stream` and the LangGraph agentic graph) emit
frames through `sse_event`/`stage_event`, and every consumer (Streamlit's
`_parse_sse`, the contract test) parses through `parse_sse`. Keeping the framing in
one place is what lets the characterization test guard the seam against event-shape
drift when the orchestration underneath changes."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable, Iterator
from typing import Any


def sse_event(event: dict[str, Any]) -> str:
    """Serialise one event dict to an SSE frame. `event['type']` is the event name."""
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


def stage_event(stage: str, message: str) -> str:
    """A `stage` frame: a named pipeline step with a human-readable message."""
    return sse_event({"type": "stage", "stage": stage, "message": message})


def parse_sse(stream: Iterable[str]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (event_name, data_dict) pairs from a stream of SSE frame strings."""
    event_type = ""
    for chunk in stream:
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                with contextlib.suppress(json.JSONDecodeError):
                    yield event_type, json.loads(line[6:])
