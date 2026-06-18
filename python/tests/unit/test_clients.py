"""Tests for the adapter factory (graceful degradation, Q7)."""

from __future__ import annotations

from app.core.clients import build_adapters
from app.core.config import Settings


def test_force_fixtures_bundle():
    a = build_adapters(force_fixtures=True)
    assert a.live_agent is True
    for name in ("sec", "market", "llm", "vector", "universe"):
        assert getattr(a, name) is not None


def test_no_keys_falls_back_to_fixtures():
    # No secrets -> real adapter modules absent/uninitialised -> fixtures fill in.
    a = build_adapters(Settings(gemini_api_key="", pinecone_api_key=""))
    assert a.live_agent is False  # no Gemini key
    for name in ("sec", "market", "llm", "vector", "universe"):
        assert getattr(a, name) is not None
