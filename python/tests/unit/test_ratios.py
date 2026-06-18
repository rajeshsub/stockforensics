"""Unit tests for pure numeric helpers."""

from __future__ import annotations

import math

import pytest

from app.transform import ratios as R


def test_safe_div():
    assert R.safe_div(10, 2) == 5
    assert R.safe_div(10, 0) is None
    assert R.safe_div(None, 2) is None
    assert R.safe_div(10, None) is None


def test_window():
    assert R.window([1, 2, 3, 4, 5], 3) == [3, 4, 5]
    assert R.window([1, 2], 5) == [1, 2]
    assert R.window([1, 2, 3], 0) == []


def test_mean_stdev_cov():
    assert R.mean([]) is None
    assert R.mean([2, 4]) == 3
    assert R.stdev([5]) is None
    assert R.stdev([1, 1, 1]) == 0
    assert math.isclose(R.stdev([2, 4]), 1.0)
    assert R.coefficient_of_variation([0, 0]) is None  # mean 0
    assert math.isclose(R.coefficient_of_variation([2, 4]), 1.0 / 3.0)


def test_cagr():
    assert R.cagr([100]) is None
    assert R.cagr([0, 100]) is None  # non-positive start
    assert R.cagr([-1, 100]) is None
    assert math.isclose(R.cagr([100, 121]), 0.21, rel_tol=1e-9)
    assert math.isclose(R.cagr([100, 110, 121]), 0.1, rel_tol=1e-9)


def test_ols_slope():
    assert R.ols_slope([1]) is None
    assert math.isclose(R.ols_slope([1, 2, 3]), 1.0)
    assert math.isclose(R.ols_slope([3, 2, 1]), -1.0)
    assert R.ols_slope([5, 5, 5]) == 0


def test_fraction_positive():
    assert R.fraction_positive([]) is None
    assert R.fraction_positive([1, -1, 1, 1]) == 0.75
    assert R.fraction_positive([-1, -2]) == 0


def test_max_yoy_decline():
    assert R.max_yoy_decline([100]) is None
    assert R.max_yoy_decline([100, 110, 120]) == 0
    assert math.isclose(R.max_yoy_decline([100, 80, 90]), 0.2)


def test_growth():
    assert R.growth([5]) is None
    assert R.growth([0, 10]) is None
    assert math.isclose(R.growth([100, 140]), 0.4)


@pytest.mark.parametrize(
    "used,req,expected",
    [(5, 5, "5yr"), (3, 5, "3yr (5yr requested)"), (6, 5, "6yr")],
)
def test_window_label(used, req, expected):
    assert R.window_label(used, req) == expected
