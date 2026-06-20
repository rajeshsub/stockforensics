"""Ports (Protocols) for every external dependency (Q3, Q6). Real impls live
alongside; fixture impls in fixtures.py. Unit tests inject fixtures -> offline,
deterministic. Live `@smoke` tests exercise the real impls (non-gating)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class MarketData:
    ticker: str
    price: float | None = None
    market_cap: float | None = None
    pe: float | None = None
    pb: float | None = None
    current_ratio: float | None = None


@dataclass(frozen=True)
class InsiderSummary:
    ownership_pct: float | None = None  # CEO/insider beneficial ownership %
    max_sold_frac_12mo: float | None = None  # largest single-insider sell fraction / 12mo


@dataclass(frozen=True)
class GroundingCitation:
    """A source surfaced by Gemini's grounded (google_search) generation."""

    title: str
    url: str


@dataclass(frozen=True)
class Constituent:
    ticker: str
    name: str
    sector: str | None = None
    weight: float | None = None  # index weight, for info
    cik: str | None = None


@dataclass(frozen=True)
class FilingDoc:
    accession: str
    form: str  # "10-K", "DEF 14A"
    url: str
    text: str


@dataclass(frozen=True)
class VectorItem:
    id: str
    values: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class MarketClient(Protocol):
    def get_market_data(self, ticker: str) -> MarketData: ...


class SecClient(Protocol):
    def resolve_cik(self, ticker: str) -> str | None: ...
    def get_company_facts(self, cik: str) -> dict[str, Any]: ...
    def get_insider_summary(self, cik: str) -> InsiderSummary: ...
    def get_filings(self, cik: str, forms: tuple[str, ...]) -> list[FilingDoc]: ...


class LlmClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield narrative tokens as they are generated (for the thinking stream)."""
        ...

    def generate_json(self, prompt: str, *, grounded: bool = False) -> dict[str, Any]:
        """Structured output. grounded=True enables Gemini google_search web grounding
        (replaces Tavily, Q17); returned dict may include a 'citations' list."""
        ...

    def generate_text(self, prompt: str) -> str:
        """Plain-prose completion (no grounding, no JSON) for short rationales."""
        ...


class VectorClient(Protocol):
    def upsert(self, namespace: str, items: list[VectorItem]) -> None: ...
    def query(self, namespace: str, vector: list[float], top_k: int = 5) -> list[VectorMatch]: ...


class UniverseClient(Protocol):
    def fetch_constituents(self) -> list[Constituent]: ...
