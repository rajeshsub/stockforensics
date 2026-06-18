"""Adapter bundle + factory. Per-key graceful degradation (Q7): when a secret is
absent, that adapter falls back to the offline fixture so the batch still runs and
simply skips the live stage. Real impls are imported lazily to avoid hard deps at
import time."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters import fixtures as fx
from app.adapters.protocols import (
    LlmClient,
    MarketClient,
    SecClient,
    UniverseClient,
    VectorClient,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger("clients")


@dataclass
class Adapters:
    sec: SecClient
    market: MarketClient
    llm: LlmClient
    vector: VectorClient
    universe: UniverseClient
    live_agent: bool = False  # True when the agent can run (Gemini key, or fixtures)


def _fixtures() -> Adapters:
    return Adapters(
        sec=fx.FixtureSecClient(),
        market=fx.FixtureMarketClient(),
        llm=fx.FixtureLlmClient(),
        vector=fx.FixtureVectorClient(),
        universe=fx.FixtureUniverseClient(),
        live_agent=True,  # fixture agent is fully deterministic + available
    )


def build_adapters(settings: Settings | None = None, *, force_fixtures: bool = False) -> Adapters:
    """Assemble adapters. Live impls used where keys exist; fixtures fill the gaps."""
    s = settings or get_settings()
    if force_fixtures:
        return _fixtures()

    a = _fixtures()  # start from safe offline defaults, override where live is possible

    # Live impls are wired here as they become configured. Missing key -> keep fixture.
    try:
        if s.sec_user_agent:
            from app.adapters.sec_client import HttpxSecClient

            a.sec = HttpxSecClient(s.sec_user_agent)
        from app.adapters.market_client import YFinanceMarketClient

        a.market = YFinanceMarketClient()
        from app.adapters.universe_client import ISharesUniverseClient

        a.universe = ISharesUniverseClient(s)
    except Exception as e:  # pragma: no cover - defensive, exercised via smoke
        log.warning("live_data_adapters_unavailable", error=str(e))

    live_llm = bool(s.gemini_api_key)
    try:
        if live_llm:
            from app.adapters.llm_client import GeminiLlmClient

            a.llm = GeminiLlmClient(s)  # web/news via built-in google_search grounding
        if s.pinecone_api_key:
            from app.adapters.vector_client import PineconeVectorClient

            a.vector = PineconeVectorClient(s)
    except Exception as e:  # pragma: no cover - defensive, exercised via smoke
        log.warning("live_ai_adapters_unavailable", error=str(e))

    # The agent needs an LLM; without a Gemini key we skip live synthesis but the
    # deterministic fixture agent still supplies (demo) findings when offline.
    a.live_agent = live_llm
    return a
