"""WeightedScorer: the pure, deterministic scoring engine (Q2, Q9, Q12).

One renormalisation path handles BOTH user-disabled and NA-dropped criteria.
No I/O, no LLM, no network -> trivially unit-testable. The FastAPI recalc endpoint
is a thin shell over score_all() on stored CompanyFinancials inputs."""

from __future__ import annotations

from app.transform.models import (
    CompanyFinancials,
    ScoredCriterion,
    ScoringDimension,
    Status,
)
from app.transform.scoring_rules import DIMENSIONS

# user_weights per dimension: {criterion_key: weight} ; value None => disabled.
DimWeights = dict[str, float | None]


def score_dimension(
    dim_key: str,
    cd: CompanyFinancials,
    user_weights: DimWeights | None = None,
) -> ScoringDimension:
    """Score one dimension. user_weights overrides default weights; a key mapped
    to None is disabled. NA criteria are dropped; enabled weights renormalise."""
    spec = DIMENSIONS[dim_key]
    defaults = spec.default_weights
    uw: DimWeights = user_weights or {}

    results = {c.key: c.evaluate(cd) for c in spec.criteria}

    # Determine the active pool (enabled AND not NA) + their raw weights.
    raw_w: dict[str, float] = {}
    for c in spec.criteria:
        disabled = c.key in uw and uw[c.key] is None
        if disabled or results[c.key].status == Status.NA:
            continue
        w = uw.get(c.key)
        raw_w[c.key] = float(w) if w is not None else defaults[c.key]
    total = sum(raw_w.values())

    dim = ScoringDimension(name=spec.name, nominal_max=spec.nominal_max)
    for c in spec.criteria:
        res = results[c.key]
        disabled = c.key in uw and uw[c.key] is None
        active = c.key in raw_w

        if active and total > 0:
            norm_w = raw_w[c.key] / total
            max_points = spec.nominal_max * norm_w
            frac = (
                res.earned_fraction
                if res.earned_fraction is not None
                else (1.0 if res.status == Status.PASS else 0.0)
            )
            earned = max_points * frac
            status = res.status
            reason = res.reason
            dim.score += earned
            dim.max_score += max_points
            dim.confidence += defaults[c.key]
        else:
            max_points = 0.0
            earned = 0.0
            status = Status.NA if disabled else res.status
            reason = "disabled by user" if disabled else res.reason

        dim.criteria.append(
            ScoredCriterion(
                key=c.key,
                label=c.label,
                default_weight=defaults[c.key],
                provenance=c.provenance,
                status=status,
                raw_value=res.raw_value,
                window_used=res.window_used,
                reason=reason,
                max_points=max_points,
                earned_points=earned,
                source_urls=res.source_urls,
            )
        )

    dim.normalized_pct = (100.0 * dim.score / dim.max_score) if dim.max_score > 0 else 0.0
    return dim


def score_all(
    cd: CompanyFinancials,
    user_weights: dict[str, DimWeights] | None = None,
) -> dict[str, ScoringDimension]:
    """Score every dimension. user_weights keyed by dimension."""
    uw = user_weights or {}
    return {dim_key: score_dimension(dim_key, cd, uw.get(dim_key)) for dim_key in DIMENSIONS}


# The 4 fully-deterministic dimensions (Promoter is hybrid + live-on-selection, Q22).
DETERMINISTIC_DIMS = ("graham", "buffett", "munger", "earnings_quality")


def composite_pct(dims: dict[str, ScoringDimension]) -> float:
    """Full composite across all available dimensions (detail view, incl. Promoter)."""
    vals = [d.normalized_pct for d in dims.values() if d.max_score > 0]
    return sum(vals) / len(vals) if vals else 0.0


def deterministic_composite(dims: dict[str, ScoringDimension]) -> float:
    """Leaderboard composite: 4 deterministic dims only, so rows stay comparable (Q22)."""
    vals = [
        dims[k].normalized_pct for k in DETERMINISTIC_DIMS if k in dims and dims[k].max_score > 0
    ]
    return sum(vals) / len(vals) if vals else 0.0
