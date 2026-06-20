"""Deterministic in-memory fixtures. Double as (a) unit-test doubles and (b) the
keyless offline demo/seed source. No network, no secrets, fully reproducible."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Any

from app.adapters.protocols import (
    Constituent,
    FilingDoc,
    InsiderSummary,
    MarketData,
    VectorItem,
    VectorMatch,
)
from app.transform.xbrl_map import PRETAX_TAG

EMBED_DIM = 8


def _facts(
    entity: str, cik: str, series: dict[str, list[float]], start_fy: int = 2021
) -> dict[str, Any]:
    gaap: dict[str, Any] = {}
    for concept, vals in series.items():
        unit = "USD/shares" if concept.startswith("EarningsPerShare") else "USD"
        pts = [
            {
                "end": f"{start_fy + i}-09-30",
                "val": v,
                "fy": start_fy + i,
                "fp": "FY",
                "form": "10-K",
            }
            for i, v in enumerate(vals)
        ]
        gaap[concept] = {"units": {unit: pts}}
    return {"cik": cik, "entityName": entity, "facts": {"us-gaap": gaap}}


_AAPL = _facts(
    "Apple Inc.",
    "0000320193",
    {
        "RevenueFromContractWithCustomerExcludingAssessedTax": [350, 360, 370, 385, 400],
        "CostOfRevenue": [200, 205, 208, 214, 220],
        "NetIncomeLoss": [66, 70, 74, 80, 86],
        "StockholdersEquity": [320, 330, 340, 350, 360],
        "Assets": [340, 350, 360, 370, 400],
        "AssetsCurrent": [130, 134, 138, 142, 150],
        "LiabilitiesCurrent": [60, 62, 63, 66, 70],
        "NetCashProvidedByUsedInOperatingActivities": [90, 95, 100, 108, 115],
        "PaymentsToAcquirePropertyPlantAndEquipment": [10, 11, 11, 12, 13],
        "EarningsPerShareDiluted": [3.0, 3.3, 3.6, 4.0, 4.4],
        "PaymentsOfDividendsCommonStock": [14, 14, 15, 15, 15],
        "Goodwill": [5, 5, 5, 6, 6],
        "InventoryNet": [5, 5, 5, 5, 6],
        "AccountsReceivableNetCurrent": [20, 21, 22, 23, 24],
        "LongTermDebtNoncurrent": [100, 100, 95, 90, 85],
        PRETAX_TAG: [
            80,
            86,
            90,
            98,
            106,
        ],
    },
)

_MSFT = _facts(
    "Microsoft Corp.",
    "0000789019",
    {
        "RevenueFromContractWithCustomerExcludingAssessedTax": [180, 190, 205, 212, 225],
        "CostOfRevenue": [60, 64, 68, 70, 74],
        "NetIncomeLoss": [60, 66, 70, 72, 75],
        "StockholdersEquity": [140, 150, 160, 170, 180],
        "Assets": [300, 320, 340, 360, 380],
        "AssetsCurrent": [160, 165, 170, 175, 180],
        "LiabilitiesCurrent": [88, 90, 92, 95, 100],
        "NetCashProvidedByUsedInOperatingActivities": [70, 76, 80, 84, 88],
        "PaymentsToAcquirePropertyPlantAndEquipment": [20, 22, 24, 26, 28],
        "EarningsPerShareDiluted": [8.0, 8.5, 9.0, 9.2, 9.6],
        "PaymentsOfDividendsCommonStock": [2, 2, 2, 2, 2],
        "Goodwill": [40, 42, 44, 46, 48],
        "InventoryNet": [3, 3, 3, 3, 3],
        "AccountsReceivableNetCurrent": [30, 31, 32, 33, 34],
        "LongTermDebtNoncurrent": [60, 62, 64, 66, 70],
        PRETAX_TAG: [
            72,
            79,
            84,
            86,
            90,
        ],
    },
)

_FACTS_BY_CIK = {"0000320193": _AAPL, "0000789019": _MSFT}
_CIK_BY_TICKER = {"AAPL": "0000320193", "MSFT": "0000789019"}

_MARKET = {
    "AAPL": MarketData("AAPL", price=245.0, market_cap=2_980_000_000_000, pe=12.5, pb=1.2),
    "MSFT": MarketData("MSFT", price=430.0, market_cap=3_100_000_000_000, pe=28.0, pb=6.0),
}
_INSIDER = {
    "AAPL": InsiderSummary(ownership_pct=0.83, max_sold_frac_12mo=0.10),
    "MSFT": InsiderSummary(ownership_pct=1.20, max_sold_frac_12mo=0.05),
}

# Promoter evidence the agent would emit (consumed + thresholded by code).
_PROMOTER_FINDINGS: dict[str, list[dict[str, Any]]] = {
    "AAPL": [
        {
            "criterion": "ceo_tenure",
            "value": 13,
            "finding": "CEO since 2011",
            "source_urls": ["https://example.com/aapl-proxy"],
        },
        {"criterion": "public_co_experience", "value": True, "finding": "prior exec roles"},
        {"criterion": "sec_enforcement", "severity": "none", "finding": "no enforcement found"},
        {"criterion": "criminal_record", "severity": "none", "finding": "no convictions found"},
        {"criterion": "related_party", "severity": "low", "value": 1, "finding": "1 minor item"},
    ],
    "MSFT": [
        {"criterion": "ceo_tenure", "value": 11, "finding": "CEO since 2014"},
        {"criterion": "public_co_experience", "value": True, "finding": "prior exec roles"},
        {"criterion": "sec_enforcement", "severity": "none", "finding": "no enforcement found"},
        {"criterion": "criminal_record", "severity": "none", "finding": "no convictions found"},
        {"criterion": "related_party", "severity": "none", "value": 0, "finding": "none disclosed"},
    ],
}

SAMPLE_TICKERS = ("AAPL", "MSFT")
_SECTOR = {"AAPL": "Technology", "MSFT": "Technology"}


class FixtureSecClient:
    def resolve_cik(self, ticker: str) -> str | None:
        return _CIK_BY_TICKER.get(ticker.upper())

    def get_company_facts(self, cik: str) -> dict[str, Any]:
        return _FACTS_BY_CIK.get(cik, {"facts": {"us-gaap": {}}})

    def get_insider_summary(self, cik: str) -> InsiderSummary:
        ticker = next((t for t, c in _CIK_BY_TICKER.items() if c == cik), "")
        return _INSIDER.get(ticker, InsiderSummary())

    def get_filings(self, cik: str, forms: tuple[str, ...]) -> list[FilingDoc]:
        ticker = next((t for t, c in _CIK_BY_TICKER.items() if c == cik), "?")
        return [
            FilingDoc(
                f"{cik}-10K",
                "10-K",
                f"https://sec.gov/{cik}/10k",
                f"{ticker} 10-K. Risk factors. MD&A. Operating performance stable.",
            ),
            FilingDoc(
                f"{cik}-DEF14A",
                "DEF 14A",
                f"https://sec.gov/{cik}/def14a",
                f"{ticker} proxy. Executive bios. Related-party transactions: minimal.",
            ),
        ]


class FixtureMarketClient:
    def get_market_data(self, ticker: str) -> MarketData:
        return _MARKET.get(ticker.upper(), MarketData(ticker.upper()))


class FixtureLlmClient:
    """Deterministic embeddings (hash-based) + fixed structured/streamed agent output."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            out.append([h[i] / 255.0 for i in range(EMBED_DIM)])
        return out

    def _narrative(self, prompt: str) -> str:
        ticker = next((t for t in SAMPLE_TICKERS if t in prompt), "AAPL")
        return f"{ticker}: deterministic fixture synthesis. Stable fundamentals, durable moat."

    def generate_stream(self, prompt: str) -> Iterator[str]:
        for word in self._narrative(prompt).split():
            yield word + " "

    def generate_text(self, prompt: str) -> str:
        ticker = next((t for t in SAMPLE_TICKERS if t in prompt), "AAPL")
        return (
            f"**{ticker} lands mid-pack on the deterministic screen.** Fixture composite "
            "rationale: value and quality dimensions carry the score while governance is neutral."
        )

    def generate_json(self, prompt: str, *, grounded: bool = False) -> dict[str, Any]:
        ticker = next((t for t in SAMPLE_TICKERS if t in prompt), "AAPL")
        return {
            "narrative": self._narrative(prompt),
            "promoter_findings": _PROMOTER_FINDINGS.get(ticker, []),
            "citations": [{"title": f"{ticker} source", "url": "https://example.com/ground/1"}],
        }


class FixtureVectorClient:
    def __init__(self) -> None:
        self._store: dict[str, list[VectorItem]] = {}

    def upsert(self, namespace: str, items: list[VectorItem]) -> None:
        self._store.setdefault(namespace, []).extend(items)

    def query(self, namespace: str, vector: list[float], top_k: int = 5) -> list[VectorMatch]:
        items = self._store.get(namespace, [])

        def cos(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            na = sum(x * x for x in a) ** 0.5 or 1.0
            nb = sum(y * y for y in b) ** 0.5 or 1.0
            return dot / (na * nb)

        ranked = sorted(items, key=lambda it: cos(vector, it.values), reverse=True)
        return [VectorMatch(it.id, cos(vector, it.values), it.metadata) for it in ranked[:top_k]]


class FixtureUniverseClient:
    def fetch_constituents(self) -> list[Constituent]:
        return [
            Constituent("AAPL", "Apple Inc.", "Technology", 0.07, "0000320193"),
            Constituent("MSFT", "Microsoft Corp.", "Technology", 0.065, "0000789019"),
        ]


def sector_of(ticker: str) -> str | None:
    return _SECTOR.get(ticker.upper())


def promoter_findings_of(ticker: str) -> list[dict[str, Any]]:
    return _PROMOTER_FINDINGS.get(ticker.upper(), [])
