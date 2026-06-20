"""Persistence helpers: store scored companies, read for the API + recalc."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import CompanyScore
from app.transform.models import CompanyFinancials, ScoringDimension
from app.transform.weighted_scorer import deterministic_composite

DIMENSION_KEYS = ("graham", "buffett", "munger", "earnings_quality", "promoter_integrity")


def financials_to_inputs(cd: CompanyFinancials) -> dict[str, Any]:
    return asdict(cd)


def inputs_to_financials(inputs: dict[str, Any]) -> CompanyFinancials:
    fields = CompanyFinancials.__dataclass_fields__
    return CompanyFinancials(**{k: v for k, v in inputs.items() if k in fields})


def save_company_score(
    session: Session,
    cd: CompanyFinancials,
    dims: dict[str, ScoringDimension],
    *,
    name: str | None = None,
    cik: str | None = None,
    narrative: str | None = None,
    composite_narrative: str | None = None,
    reasoning: str | None = None,
    promoter_live: bool = False,
    citations: list[Any] | None = None,
    thinking: list[Any] | None = None,
) -> CompanyScore:
    """Insert/replace a company's scores. composite_pct is the 4-dim deterministic
    leaderboard composite (Q22); promoter_live marks a live-AI result (Q21)."""
    session.execute(delete(CompanyScore).where(CompanyScore.ticker == cd.ticker))
    row = CompanyScore(
        ticker=cd.ticker,
        cik=cik,
        name=name,
        sector=cd.sector,
        composite_pct=round(deterministic_composite(dims), 2),
        promoter_live=promoter_live,
        market_cap=cd.market_cap,
        scores={k: v.to_dict() for k, v in dims.items()},
        inputs=financials_to_inputs(cd),
        narrative=narrative,
        composite_narrative=composite_narrative,
        reasoning=reasoning,
        promoter_findings=cd.promoter_findings,
        citations=citations or [],
        thinking=thinking or [],
    )
    session.add(row)
    session.flush()
    return row


def list_companies(session: Session) -> list[CompanyScore]:
    return list(
        session.execute(select(CompanyScore).order_by(CompanyScore.composite_pct.desc()))
        .scalars()
        .all()
    )


def get_company(session: Session, ticker: str) -> CompanyScore | None:
    return session.execute(
        select(CompanyScore).where(CompanyScore.ticker == ticker.upper())
    ).scalar_one_or_none()


def rankings(session: Session, dimension: str) -> list[dict[str, Any]]:
    """Companies ranked by a dimension's normalized_pct (Q12), with confidence."""
    out = []
    for c in list_companies(session):
        dim = c.scores.get(dimension)
        if not dim:
            continue
        out.append(
            {
                "ticker": c.ticker,
                "name": c.name,
                "score": dim["score"],
                "max_score": dim["max_score"],
                "normalized_pct": dim["normalized_pct"],
                "confidence": dim["confidence"],
            }
        )
    out.sort(key=lambda r: (r["normalized_pct"], r["confidence"]), reverse=True)
    return out


def distribution(session: Session, dimension: str) -> list[float]:
    vals = []
    for c in list_companies(session):
        dim = c.scores.get(dimension)
        if dim:
            vals.append(dim["normalized_pct"])
    return vals
