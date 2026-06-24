"""Unit tests for individual criterion evaluators (thresholds, NA, window-degrade)."""

from __future__ import annotations

import pytest

from app.transform import scoring_rules as SR
from app.transform.models import CompanyFinancials, Status


def _cd(**kw) -> CompanyFinancials:
    return CompanyFinancials(ticker="X", **kw)


def test_pe_pass_fail_na():
    assert SR.ev_pe(_cd(pe=12.0)).status is Status.PASS
    assert SR.ev_pe(_cd(pe=20.0)).status is Status.FAIL
    assert SR.ev_pe(_cd(pe=None)).status is Status.NA


def test_de_na_when_equity_undefined():
    assert SR.ev_de(_cd(debt_to_equity=None)).status is Status.NA
    assert SR.ev_de(_cd(debt_to_equity=0.4)).status is Status.PASS


def test_positive_eps_window_degrade():
    r = SR.ev_positive_eps(_cd(eps=[1, 2, 3]))  # only 3yr available
    assert r.status is Status.PASS
    assert r.window_used == "3yr (5yr requested)"


def test_positive_eps_na_when_empty():
    assert SR.ev_positive_eps(_cd(eps=[])).status is Status.NA


def test_eps_growth_floor_and_na():
    assert SR.ev_eps_growth(_cd(eps=[5])).status is Status.NA  # below growth floor
    assert SR.ev_eps_growth(_cd(eps=[0, 5])).status is Status.NA  # non-positive start
    assert SR.ev_eps_growth(_cd(eps=[5, 6])).status is Status.PASS


def test_roe_consistency_threshold():
    assert SR.ev_roe_consistency(_cd(roe=[18, 19, 20])).status is Status.PASS
    assert SR.ev_roe_consistency(_cd(roe=[5, 6, 7])).status is Status.FAIL  # mean < 15
    assert SR.ev_roe_consistency(_cd(roe=[18, 19])).status is Status.NA  # below floor


def test_fcf_consistency():
    assert SR.ev_fcf_consistency(_cd(fcf=[1, 2, 3, 4, 5])).status is Status.PASS
    assert SR.ev_fcf_consistency(_cd(fcf=[-1, -2, 3])).status is Status.FAIL


def test_goodwill_low_na_and_threshold():
    assert SR.ev_goodwill_low(_cd(goodwill=None, total_assets=100)).status is Status.NA
    assert SR.ev_goodwill_low(_cd(goodwill=10, total_assets=100)).status is Status.PASS
    assert SR.ev_goodwill_low(_cd(goodwill=40, total_assets=100)).status is Status.FAIL


def test_nonrecurring_na_when_empty():
    assert SR.ev_no_nonrecurring_abuse(_cd(special_items=[], pretax_income=[])).status is Status.NA


def test_munger_value_na_without_peers():
    assert SR.ev_munger_value(_cd(sector_peer_count=0)).status is Status.NA
    r = SR.ev_munger_value(
        _cd(sector_peer_count=8, sector_pe_percentile=0.2, sector_pb_percentile=0.2)
    )
    assert r.status is Status.PASS
    assert r.earned_fraction is not None and r.earned_fraction > 0.7


def test_munger_quality_continuous():
    r = SR.ev_munger_quality(_cd(roe=[20, 20, 20], gross_margin=[50, 50, 50]))
    assert r.status is Status.PASS
    # (20/25)*5 + (50/50)*5 = 9.0 -> fraction 0.9
    assert r.earned_fraction == pytest.approx(0.9)


def test_munger_quality_falls_back_to_net_margin_for_banks():
    # Banks file no cost-of-revenue -> no gross margin. Net margin keeps Quality scorable
    # instead of NA'ing the whole Munger dimension (the JPM "0%" bug).
    r = SR.ev_munger_quality(_cd(roe=[20, 20, 20], gross_margin=[], net_margin=[25, 25, 25]))
    assert r.status is Status.PASS
    # (20/25)*5 + (25/25)*5 = 9.0 -> fraction 0.9
    assert r.earned_fraction == pytest.approx(0.9)
    assert "NM" in (r.reason or "")


def test_munger_quality_na_without_any_margin():
    assert SR.ev_munger_quality(_cd(roe=[20, 20, 20], gross_margin=[], net_margin=[])).status is (
        Status.NA
    )


def test_ownership_code():
    assert SR.ev_ownership(_cd(insider_ownership_pct=2.0)).status is Status.PASS
    assert SR.ev_ownership(_cd(insider_ownership_pct=0.5)).status is Status.FAIL
    assert SR.ev_ownership(_cd(insider_ownership_pct=None)).status is Status.NA


def test_promoter_llm_evidence_missing_is_na():
    # No findings -> not checked -> NA (graceful degradation when agent skipped)
    assert SR.ev_no_sec_enforcement(_cd(promoter_findings=[])).status is Status.NA


def test_promoter_adverse_severity_fails():
    cd = _cd(promoter_findings=[{"criterion": "sec_enforcement", "severity": "high"}])
    assert SR.ev_no_sec_enforcement(cd).status is Status.FAIL
    cd2 = _cd(promoter_findings=[{"criterion": "sec_enforcement", "severity": "none"}])
    assert SR.ev_no_sec_enforcement(cd2).status is Status.PASS


def test_ceo_tenure_threshold_and_urls():
    cd = _cd(promoter_findings=[{"criterion": "ceo_tenure", "value": 13, "source_urls": ["u"]}])
    r = SR.ev_ceo_tenure(cd)
    assert r.status is Status.PASS
    assert r.source_urls == ("u",)
    assert (
        SR.ev_ceo_tenure(_cd(promoter_findings=[{"criterion": "ceo_tenure", "value": 2}])).status
        is Status.FAIL
    )


def test_dimensions_default_weights_sum_to_one():
    for spec in SR.DIMENSIONS.values():
        assert abs(sum(spec.default_weights.values()) - 1.0) < 1e-9
