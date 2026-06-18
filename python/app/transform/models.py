"""Domain models for the deterministic scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

Provenance = Literal["CODE", "LLM-EVIDENCE"]


class Status(StrEnum):
    """Three-state criterion outcome (Q9)."""

    PASS = "PASS"  # nosec B105
    FAIL = "FAIL"
    NA = "NA"

    @property
    def symbol(self) -> str:
        return {Status.PASS: "✓", Status.FAIL: "✗", Status.NA: "–"}[self]


@dataclass(frozen=True)
class CriterionResult:
    """Evaluation output for one criterion (before weighting).

    earned_fraction lets continuous criteria (e.g. Munger sub-scores) earn a
    portion of their max points. None => boolean: PASS earns 1.0, FAIL earns 0.0.
    """

    status: Status
    raw_value: str | float | None = None
    window_used: str | None = None
    reason: str | None = None
    earned_fraction: float | None = None
    source_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoredCriterion:
    """A criterion after weighting/normalisation within a dimension."""

    key: str
    label: str
    default_weight: float
    provenance: Provenance
    status: Status
    raw_value: str | float | None
    window_used: str | None
    reason: str | None
    max_points: float  # available points (0 if NA/disabled)
    earned_points: float  # max_points if PASS else 0
    source_urls: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "criterion": self.label,
            "weight": round(self.default_weight, 4),
            "provenance": self.provenance,
            "status": self.status.value,
            "symbol": self.status.symbol,
            "value": self.raw_value,
            "window_used": self.window_used,
            "reason": self.reason,
            "max_points": round(self.max_points, 3),
            "earned": round(self.earned_points, 3),
            "url": list(self.source_urls),
        }


@dataclass
class ScoringDimension:
    """A complete weighted score for one dimension."""

    name: str
    nominal_max: float  # 7.0 or 10.0 when all criteria enabled+available
    criteria: list[ScoredCriterion] = field(default_factory=list)
    score: float = 0.0
    max_score: float = 0.0  # available points (PASS + FAIL)
    normalized_pct: float = 0.0  # 100 * score / max_score
    confidence: float = 0.0  # fraction of nominal weight evaluated (non-NA, enabled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "max_score": round(self.max_score, 2),
            "nominal_max": self.nominal_max,
            "normalized_pct": round(self.normalized_pct, 1),
            "confidence": round(self.confidence, 3),
            "breakdown": [c.to_dict() for c in self.criteria],
        }


@dataclass
class CompanyFinancials:
    """Inputs for deterministic scoring. Year series ordered oldest -> newest.

    All fields Optional / possibly-short; the scorer handles NA + window-degrade.
    Promoter findings come from the agent (LLM-EVIDENCE) and are thresholded by code.
    """

    ticker: str
    sector: str | None = None

    # Current market data (yfinance)
    pe: float | None = None
    pb: float | None = None
    current_ratio: float | None = None
    market_cap: float | None = None

    # Latest-point fundamentals
    debt_to_equity: float | None = None  # latest
    equity_latest: float | None = None
    goodwill: float | None = None
    total_assets: float | None = None

    # Year series (oldest -> newest)
    eps: list[float] = field(default_factory=list)
    dividends: list[float] = field(default_factory=list)
    roe: list[float] = field(default_factory=list)  # percent, e.g. 18.0
    net_margin: list[float] = field(default_factory=list)  # percent
    gross_margin: list[float] = field(default_factory=list)  # percent
    revenue: list[float] = field(default_factory=list)
    fcf: list[float] = field(default_factory=list)
    ocf: list[float] = field(default_factory=list)
    net_income: list[float] = field(default_factory=list)
    capex: list[float] = field(default_factory=list)
    receivables: list[float] = field(default_factory=list)
    inventory: list[float] = field(default_factory=list)
    de_series: list[float] = field(default_factory=list)  # debt/equity per year
    special_items: list[float] = field(default_factory=list)
    pretax_income: list[float] = field(default_factory=list)

    # Earnings-quality soft inputs
    auditor_years: int | None = None  # consecutive years same auditor

    # Promoter inputs
    insider_ownership_pct: float | None = None  # CODE: Form 3/4/5 / DEF 14A
    insider_max_sold_frac_12mo: float | None = None  # CODE: Form 4
    promoter_findings: list[dict[str, Any]] = field(default_factory=list)  # LLM-EVIDENCE

    # Peer context for Munger value sub-score (filled by pipeline)
    sector_pe_percentile: float | None = None  # 0..1, lower = cheaper
    sector_pb_percentile: float | None = None
    sector_peer_count: int = 0

    def reference_urls(self) -> dict[str, list[str]]:
        return {}
