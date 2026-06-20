"""Unit tests for the WeightedScorer (renormalize, disable, NA, recalc, composite)."""

from __future__ import annotations

import pytest

from app.transform.models import Status
from app.transform.weighted_scorer import (
    composite_pct,
    deterministic_composite,
    score_all,
    score_dimension,
)


def test_deterministic_composite_excludes_promoter(aapl):
    dims = score_all(aapl)
    det = deterministic_composite(dims)
    full = composite_pct(dims)
    # deterministic excludes promoter -> differs from full (promoter != avg of the 4)
    assert 0 <= det <= 100
    assert det != full


def test_aapl_graham_perfect(aapl):
    d = score_dimension("graham", aapl)
    assert d.score == pytest.approx(6.0)
    assert d.max_score == pytest.approx(6.0)
    assert d.normalized_pct == pytest.approx(100.0)
    assert d.confidence == pytest.approx(1.0)


def test_msft_graham_fails_some(msft):
    d = score_dimension("graham", msft)
    assert d.score < 6.0
    # P/E 28, P/B 6, current-ratio 1.8 all fail
    fails = {c.key for c in d.criteria if c.status is Status.FAIL}
    assert {"pe_below_15", "pb_below_1_5", "current_ratio_gt_2"} <= fails


def test_disabling_failing_criterion_raises_pct(msft):
    base = score_dimension("graham", msft)
    # disable a failing criterion -> remaining renormalize -> pct should rise
    better = score_dimension("graham", msft, {"pe_below_15": None})
    assert better.normalized_pct > base.normalized_pct
    assert better.confidence < base.confidence  # fewer criteria evaluated


def test_na_criterion_renormalizes_and_lowers_confidence(aapl):
    # special_items empty -> no_nonrecurring_abuse NA -> dropped, conf < 1
    d = score_dimension("earnings_quality", aapl)
    na = [c for c in d.criteria if c.status is Status.NA]
    assert any(c.key == "no_nonrecurring_abuse" for c in na)
    assert d.confidence < 1.0
    assert d.max_score < d.nominal_max  # one criterion dropped


def test_custom_weights_renormalize(aapl):
    # Heavily upweight P/E; score stays within bounds, weights normalise internally
    d = score_dimension("graham", aapl, {"pe_below_15": 0.9})
    assert 0 <= d.score <= d.max_score
    active = [c for c in d.criteria if c.max_points > 0]
    assert abs(sum(c.max_points for c in active) - d.max_score) < 1e-9


def test_score_all_has_five_dimensions(aapl):
    r = score_all(aapl)
    assert set(r) == {"graham", "buffett", "munger", "earnings_quality", "promoter_integrity"}


def test_recalc_is_deterministic(aapl):
    a = score_all(aapl)
    b = score_all(aapl)
    assert {k: v.score for k, v in a.items()} == {k: v.score for k, v in b.items()}


def test_composite_pct(aapl):
    c = composite_pct(score_all(aapl))
    assert 0 <= c <= 100


def test_promoter_hybrid_mixes_provenance(aapl):
    d = score_dimension("promoter_integrity", aapl)
    provs = {c.provenance for c in d.criteria}
    assert provs == {"CODE", "LLM-EVIDENCE"}
    # ownership 0.83% < 1% -> fail
    own = next(c for c in d.criteria if c.key == "ownership_ge_1pct")
    assert own.status is Status.FAIL


def test_all_disabled_yields_zero(aapl):
    weights = {c.key: None for c in score_dimension("graham", aapl).criteria}
    d = score_dimension("graham", aapl, weights)
    assert d.score == 0.0
    assert d.max_score == 0.0
    assert d.normalized_pct == 0.0
    assert d.confidence == 0.0


def test_dimension_to_dict_shape(aapl):
    d = score_dimension("graham", aapl).to_dict()
    assert {"name", "score", "max_score", "normalized_pct", "confidence", "breakdown"} <= set(d)
    row = d["breakdown"][0]
    assert {"key", "criterion", "provenance", "status", "value", "max_points", "earned"} <= set(row)
