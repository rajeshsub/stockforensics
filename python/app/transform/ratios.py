"""Pure numeric helpers. Every function tolerates missing/short data and returns
Optional so the scorer can map undefined -> NA (Q9). No I/O, no external deps."""

from __future__ import annotations

import math
from collections.abc import Sequence


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Divide, returning None when undefined (None inputs or zero/neg denominator)."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def window(series: Sequence[float], n: int) -> list[float]:
    """Most-recent n values (series ordered oldest->newest). Shorter if fewer."""
    if n <= 0:
        return []
    return list(series[-n:])


def mean(series: Sequence[float]) -> float | None:
    """Arithmetic mean, or None if empty."""
    vals = list(series)
    if not vals:
        return None
    return sum(vals) / len(vals)


def stdev(series: Sequence[float]) -> float | None:
    """Population stdev. Needs >=2 points, else None."""
    vals = list(series)
    if len(vals) < 2:
        return None
    mu = sum(vals) / len(vals)
    var = sum((x - mu) ** 2 for x in vals) / len(vals)
    return math.sqrt(var)


def coefficient_of_variation(series: Sequence[float]) -> float | None:
    """stdev/|mean|. None if undefined (mean 0 or <2 points)."""
    mu = mean(series)
    sd = stdev(series)
    if mu is None or sd is None or mu == 0:
        return None
    return sd / abs(mu)


def cagr(series: Sequence[float]) -> float | None:
    """Compound annual growth rate over the window. Needs >=2 points and a
    positive starting value; returns fractional rate (0.08 = 8%)."""
    vals = list(series)
    if len(vals) < 2:
        return None
    start, end = vals[0], vals[-1]
    periods = len(vals) - 1
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / periods) - 1


def ols_slope(series: Sequence[float]) -> float | None:
    """Least-squares slope vs index. Needs >=2 points."""
    vals = list(series)
    n = len(vals)
    if n < 2:
        return None
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(vals) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, vals, strict=True)) / denom


def fraction_positive(series: Sequence[float]) -> float | None:
    """Fraction of values > 0. None if empty."""
    vals = list(series)
    if not vals:
        return None
    return sum(1 for v in vals if v > 0) / len(vals)


def max_yoy_decline(series: Sequence[float]) -> float | None:
    """Largest year-over-year fractional decline (positive number). Needs >=2."""
    vals = list(series)
    if len(vals) < 2:
        return None
    worst = 0.0
    for prev, cur in zip(vals, vals[1:], strict=False):
        if prev and prev > 0:
            change = (cur - prev) / prev
            if change < 0:
                worst = max(worst, -change)
    return worst


def growth(series: Sequence[float]) -> float | None:
    """Total fractional growth start->end. Needs >=2 and positive start."""
    vals = list(series)
    if len(vals) < 2 or vals[0] is None or vals[0] <= 0:
        return None
    return (vals[-1] - vals[0]) / vals[0]


def window_label(used: int, requested: int) -> str:
    """Human label for window degradation (Q9)."""
    if used >= requested:
        return f"{used}yr"
    return f"{used}yr ({requested}yr requested)"
