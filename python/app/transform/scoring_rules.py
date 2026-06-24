"""Explicit, versioned scoring rules (Q11). Every criterion is pinned to a precise
formula + numeric threshold here; the single tunable source of truth. Each
evaluator maps CompanyFinancials -> CriterionResult (PASS/FAIL/NA), handling
window-degrade and undefined inputs per Q9.

Provenance: CODE = computed from structured data; LLM-EVIDENCE = code thresholds
structured findings the agent extracted (code still owns the boolean, rule #10)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.transform import ratios as R
from app.transform.models import CompanyFinancials, CriterionResult, Provenance, Status

# --- Tunable thresholds (one place) -----------------------------------------
TH: dict[str, float] = {
    "pe_max": 15.0,
    "pb_max": 1.5,
    "current_ratio_min": 2.0,
    "de_max": 0.5,
    "roe_mean_min": 15.0,
    "roe_cov_max": 0.30,
    "gross_margin_mean_min": 40.0,
    "gross_margin_stdev_max": 5.0,
    "de_stable_max": 1.0,
    "fcf_positive_frac_min": 0.80,
    "rev_yoy_decline_max": 0.10,
    "net_margin_stdev_max": 3.0,
    "goodwill_assets_max": 0.30,
    "auditor_years_min": 3.0,
    "nonrecurring_ratio_max": 0.10,
    "receivables_excess_max": 0.10,
    "inventory_excess_max": 0.10,
    "ownership_min_pct": 1.0,
    "insider_sold_frac_max": 0.50,
    "ceo_tenure_min_years": 5.0,
    "munger_capex_rev_best": 0.05,  # <=5% -> 10
    "munger_capex_rev_worst": 0.25,  # >=25% -> 0
    "related_party_count_max": 2.0,
}

REQ_WINDOW = 5  # requested multi-year window
GROWTH_FLOOR = 2
CONSISTENCY_FLOOR = 3
LEVEL_FLOOR = 1

ADVERSE_SEVERITIES = {"medium", "high"}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(x, hi))


def _na(reason: str, urls: tuple[str, ...] = ()) -> CriterionResult:
    return CriterionResult(Status.NA, reason=reason, source_urls=urls)


def _boolean(
    passed: bool,
    raw: str | float | None,
    reason: str,
    window: str | None = None,
    urls: tuple[str, ...] = (),
) -> CriterionResult:
    return CriterionResult(
        Status.PASS if passed else Status.FAIL,
        raw_value=raw,
        window_used=window,
        reason=reason,
        source_urls=urls,
    )


def _continuous(
    sub_score_0_10: float, raw: str, reason: str, window: str | None = None
) -> CriterionResult:
    """A continuous component earning a fraction of its max points (Munger)."""
    frac = _clamp(sub_score_0_10, 0.0, 10.0) / 10.0
    return CriterionResult(
        Status.PASS, raw_value=raw, window_used=window, reason=reason, earned_fraction=frac
    )


def _finding(cd: CompanyFinancials, key: str) -> dict[str, Any] | None:
    for f in cd.promoter_findings:
        if f.get("criterion") == key:
            return f
    return None


# --- Graham (0-7), all CODE --------------------------------------------------
def ev_pe(cd: CompanyFinancials) -> CriterionResult:
    if cd.pe is None:
        return _na("P/E undefined (EPS<=0 or no price)")
    return _boolean(cd.pe < TH["pe_max"], round(cd.pe, 1), f"P/E {cd.pe:.1f} vs <{TH['pe_max']:g}")


def ev_pb(cd: CompanyFinancials) -> CriterionResult:
    if cd.pb is None:
        return _na("P/B undefined (book<=0 or no price)")
    return _boolean(cd.pb < TH["pb_max"], round(cd.pb, 2), f"P/B {cd.pb:.2f} vs <{TH['pb_max']:g}")


def ev_current_ratio(cd: CompanyFinancials) -> CriterionResult:
    if cd.current_ratio is None:
        return _na("current ratio undefined")
    return _boolean(
        cd.current_ratio > TH["current_ratio_min"],
        round(cd.current_ratio, 2),
        f"current ratio {cd.current_ratio:.2f} vs >{TH['current_ratio_min']:g}",
    )


def ev_de(cd: CompanyFinancials) -> CriterionResult:
    if cd.debt_to_equity is None:
        return _na("D/E undefined (equity<=0)")
    return _boolean(
        cd.debt_to_equity < TH["de_max"],
        round(cd.debt_to_equity, 2),
        f"D/E {cd.debt_to_equity:.2f} vs <{TH['de_max']:g}",
    )


def ev_positive_eps(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.eps, REQ_WINDOW)
    if len(w) < LEVEL_FLOOR:
        return _na("no EPS history")
    passed = all(x > 0 for x in w)
    return _boolean(
        passed,
        "Yes" if passed else "No",
        f"EPS>0 in all {len(w)}yr",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_dividend(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.dividends, REQ_WINDOW)
    if len(w) < LEVEL_FLOOR:
        return _na("no dividend history")
    passed = all(x > 0 for x in w)
    return _boolean(
        passed,
        "Yes" if passed else "No",
        f"dividend>0 in all {len(w)}yr",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_eps_growth(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.eps, REQ_WINDOW)
    if len(w) < GROWTH_FLOOR:
        return _na("need >=2yr EPS for growth")
    g = R.cagr(w)
    if g is None:
        return _na("EPS CAGR undefined (non-positive endpoint)")
    return _boolean(
        g > 0, f"{g * 100:+.1f}%", f"EPS CAGR {g * 100:+.1f}%", R.window_label(len(w), REQ_WINDOW)
    )


# --- Buffett (0-10), all CODE ------------------------------------------------
def ev_roe_consistency(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.roe, REQ_WINDOW)
    if len(w) < CONSISTENCY_FLOOR:
        return _na("need >=3yr ROE")
    m = R.mean(w)
    cv = R.coefficient_of_variation(w)
    if m is None or cv is None:
        return _na("ROE mean/cv undefined")
    passed = m >= TH["roe_mean_min"] and cv <= TH["roe_cov_max"]
    return _boolean(
        passed,
        f"μ{m:.1f}% cv{cv:.2f}",
        f"mean ROE {m:.1f}% (>={TH['roe_mean_min']:g}), cv {cv:.2f} (<={TH['roe_cov_max']})",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_net_margin_trend(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.net_margin, REQ_WINDOW)
    if len(w) < CONSISTENCY_FLOOR:
        return _na("need >=3yr net margin")
    slope = R.ols_slope(w)
    passed = (slope is not None and slope >= 0) or (w[-1] >= w[0])
    return _boolean(
        passed,
        f"slope {slope:+.2f}" if slope is not None else "n/a",
        f"net margin slope {slope:+.2f}/yr" if slope is not None else "flat",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_gross_margin_level(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.gross_margin, REQ_WINDOW)
    if len(w) < CONSISTENCY_FLOOR:
        return _na("need >=3yr gross margin")
    m = R.mean(w)
    sd = R.stdev(w)
    if m is None or sd is None:
        return _na("gross margin mean/stdev undefined")
    passed = m >= TH["gross_margin_mean_min"] and sd <= TH["gross_margin_stdev_max"]
    return _boolean(
        passed,
        f"μ{m:.1f}% σ{sd:.1f}",
        f"mean GM {m:.1f}% (>={TH['gross_margin_mean_min']:g}), σ {sd:.1f}pp",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_de_low_stable(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.de_series, REQ_WINDOW)
    if cd.debt_to_equity is None or len(w) < GROWTH_FLOOR:
        return _na("need latest D/E + >=2yr D/E history")
    passed = cd.debt_to_equity < TH["de_max"] and max(w) < TH["de_stable_max"]
    return _boolean(
        passed,
        f"now {cd.debt_to_equity:.2f} max {max(w):.2f}",
        f"latest D/E {cd.debt_to_equity:.2f} (<{TH['de_max']:g}), max {max(w):.2f}",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_fcf_consistency(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.fcf, REQ_WINDOW)
    if len(w) < CONSISTENCY_FLOOR:
        return _na("need >=3yr FCF")
    fp = R.fraction_positive(w)
    if fp is None:
        return _na("FCF fraction undefined")
    return _boolean(
        fp >= TH["fcf_positive_frac_min"],
        f"{fp * 100:.0f}% +",
        f"FCF positive in {fp * 100:.0f}% of yrs (>={TH['fcf_positive_frac_min'] * 100:g}%)",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_revenue_growth_consistency(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.revenue, REQ_WINDOW)
    if len(w) < CONSISTENCY_FLOOR:
        return _na("need >=3yr revenue")
    g = R.cagr(w)
    d = R.max_yoy_decline(w)
    if g is None or d is None:
        return _na("revenue growth undefined")
    passed = g > 0 and d <= TH["rev_yoy_decline_max"]
    return _boolean(
        passed,
        f"CAGR {g * 100:+.1f}% drop {d * 100:.0f}%",
        f"rev CAGR {g * 100:+.1f}%, worst YoY drop {d * 100:.0f}%",
        R.window_label(len(w), REQ_WINDOW),
    )


# --- Munger (0-10), continuous components ------------------------------------
def ev_munger_quality(cd: CompanyFinancials) -> CriterionResult:
    rw = R.window(cd.roe, REQ_WINDOW)
    gw = R.window(cd.gross_margin, REQ_WINDOW)
    # Banks/financials don't file cost-of-revenue, so gross margin is unavailable.
    # Fall back to net margin (with its own, lower ceiling) so the criterion still
    # scores pricing-power/profitability instead of collapsing the whole dimension to NA.
    use_gross = len(gw) >= CONSISTENCY_FLOOR
    mw = gw if use_gross else R.window(cd.net_margin, REQ_WINDOW)
    if len(rw) < CONSISTENCY_FLOOR or len(mw) < CONSISTENCY_FLOOR:
        return _na("need >=3yr ROE + (gross or net) margin")
    mr = R.mean(rw)
    mm = R.mean(mw)
    if mr is None or mm is None:
        return _na("quality inputs undefined")
    margin_ceiling, margin_label = (50.0, "GM") if use_gross else (25.0, "NM")
    sub = (mr / 25.0) * 5.0 + (mm / margin_ceiling) * 5.0
    return _continuous(
        sub,
        f"{_clamp(sub, 0, 10):.1f}/10",
        f"ROE μ{mr:.1f}%, {margin_label} μ{mm:.1f}%",
        R.window_label(min(len(rw), len(mw)), REQ_WINDOW),
    )


def ev_munger_value(cd: CompanyFinancials) -> CriterionResult:
    if (
        cd.sector_peer_count < 3
        or cd.sector_pe_percentile is None
        or cd.sector_pb_percentile is None
    ):
        return _na("need >=3 sector peers for relative value")
    avg_pct = (cd.sector_pe_percentile + cd.sector_pb_percentile) / 2.0
    sub = 10.0 * (1.0 - avg_pct)
    return _continuous(
        sub,
        f"{_clamp(sub, 0, 10):.1f}/10",
        f"cheaper than {(1 - avg_pct) * 100:.0f}% of {cd.sector_peer_count} peers",
    )


def ev_munger_capital_efficiency(cd: CompanyFinancials) -> CriterionResult:
    cw = R.window(cd.capex, REQ_WINDOW)
    rw = R.window(cd.revenue, REQ_WINDOW)
    n = min(len(cw), len(rw))
    if n < CONSISTENCY_FLOOR:
        return _na("need >=3yr capex + revenue")
    ratios = [abs(c) / r for c, r in zip(cw[-n:], rw[-n:], strict=True) if r > 0]
    ratio = R.mean(ratios)
    if ratio is None:
        return _na("capex/revenue undefined")
    best, worst = TH["munger_capex_rev_best"], TH["munger_capex_rev_worst"]
    sub = 10.0 * (worst - ratio) / (worst - best)
    return _continuous(
        sub,
        f"{_clamp(sub, 0, 10):.1f}/10",
        f"capex/rev {ratio * 100:.1f}%",
        R.window_label(n, REQ_WINDOW),
    )


# --- Earnings Quality (0-10), CODE -------------------------------------------
def ev_ocf_vs_ni(cd: CompanyFinancials) -> CriterionResult:
    ow = R.window(cd.ocf, REQ_WINDOW)
    nw = R.window(cd.net_income, REQ_WINDOW)
    n = min(len(ow), len(nw))
    if n < CONSISTENCY_FLOOR:
        return _na("need >=3yr OCF + NI")
    so, sn = sum(ow[-n:]), sum(nw[-n:])
    return _boolean(
        so >= sn,
        f"ΣOCF {so:.0f} / ΣNI {sn:.0f}",
        f"sum OCF {so:.0f} vs sum NI {sn:.0f}",
        R.window_label(n, REQ_WINDOW),
    )


def _growth_excess(numer: list[float], denom_series: list[float], cap: float) -> CriterionResult:
    g = R.growth(R.window(numer, REQ_WINDOW))
    revg = R.growth(R.window(denom_series, REQ_WINDOW))
    if g is None or revg is None:
        return _na("growth undefined (need >=2yr positive start)")
    passed = g <= revg + cap
    return _boolean(
        passed,
        f"{g * 100:+.0f}% vs rev {revg * 100:+.0f}%",
        f"growth {g * 100:+.0f}% vs revenue {revg * 100:+.0f}% +{cap * 100:g}pp",
    )


def ev_receivables_growth(cd: CompanyFinancials) -> CriterionResult:
    return _growth_excess(cd.receivables, cd.revenue, TH["receivables_excess_max"])


def ev_inventory_growth(cd: CompanyFinancials) -> CriterionResult:
    return _growth_excess(cd.inventory, cd.revenue, TH["inventory_excess_max"])


def ev_margin_stability(cd: CompanyFinancials) -> CriterionResult:
    w = R.window(cd.net_margin, REQ_WINDOW)
    if len(w) < CONSISTENCY_FLOOR:
        return _na("need >=3yr net margin")
    sd = R.stdev(w)
    if sd is None:
        return _na("net margin stdev undefined")
    return _boolean(
        sd <= TH["net_margin_stdev_max"],
        f"σ{sd:.1f}pp",
        f"net margin σ {sd:.1f}pp (<={TH['net_margin_stdev_max']:g})",
        R.window_label(len(w), REQ_WINDOW),
    )


def ev_goodwill_low(cd: CompanyFinancials) -> CriterionResult:
    r = R.safe_div(cd.goodwill, cd.total_assets)
    if r is None:
        return _na("goodwill/assets undefined")
    return _boolean(
        r < TH["goodwill_assets_max"],
        f"{r * 100:.0f}%",
        f"goodwill {r * 100:.0f}% of assets (<{TH['goodwill_assets_max'] * 100:g}%)",
    )


def ev_auditor_stable(cd: CompanyFinancials) -> CriterionResult:
    if cd.auditor_years is None:
        return _na("auditor history not parseable")
    return _boolean(
        cd.auditor_years >= TH["auditor_years_min"],
        f"{cd.auditor_years}yr",
        f"same auditor {cd.auditor_years}yr (>={TH['auditor_years_min']:g})",
    )


def ev_no_nonrecurring_abuse(cd: CompanyFinancials) -> CriterionResult:
    sw = R.window(cd.special_items, REQ_WINDOW)
    pw = R.window(cd.pretax_income, REQ_WINDOW)
    n = min(len(sw), len(pw))
    if n < CONSISTENCY_FLOOR:
        return _na("need >=3yr special items + pretax")
    ratios = [abs(s) / abs(p) for s, p in zip(sw[-n:], pw[-n:], strict=True) if p != 0]
    m = R.mean(ratios)
    if m is None:
        return _na("nonrecurring ratio undefined")
    return _boolean(
        m < TH["nonrecurring_ratio_max"],
        f"{m * 100:.0f}%",
        f"special items {m * 100:.0f}% of pretax (<{TH['nonrecurring_ratio_max'] * 100:g}%)",
        R.window_label(n, REQ_WINDOW),
    )


# --- Promoter (0-10), hybrid -------------------------------------------------
def ev_ceo_tenure(cd: CompanyFinancials) -> CriterionResult:  # LLM-EVIDENCE
    f = _finding(cd, "ceo_tenure")
    if f is None or f.get("value") is None:
        return _na("CEO tenure not found")
    yrs = float(f["value"])
    return _boolean(
        yrs >= TH["ceo_tenure_min_years"],
        f"{yrs:.0f}yr",
        f"CEO tenure {yrs:.0f}yr (>={TH['ceo_tenure_min_years']:g})",
        urls=tuple(f.get("source_urls", [])),
    )


def ev_public_co_experience(cd: CompanyFinancials) -> CriterionResult:  # LLM-EVIDENCE
    f = _finding(cd, "public_co_experience")
    if f is None or f.get("value") is None:
        return _na("public-company experience not found")
    return _boolean(
        bool(f["value"]),
        "Yes" if f["value"] else "No",
        f.get("finding", "prior public-company experience"),
        urls=tuple(f.get("source_urls", [])),
    )


def ev_ownership(cd: CompanyFinancials) -> CriterionResult:  # CODE
    if cd.insider_ownership_pct is None:
        return _na("ownership % not available")
    return _boolean(
        cd.insider_ownership_pct >= TH["ownership_min_pct"],
        f"{cd.insider_ownership_pct:.2f}%",
        f"insider ownership {cd.insider_ownership_pct:.2f}% (>={TH['ownership_min_pct']:g}%)",
    )


def ev_no_sec_enforcement(cd: CompanyFinancials) -> CriterionResult:  # LLM-EVIDENCE
    f = _finding(cd, "sec_enforcement")
    if f is None:
        return _na("not checked (no agent evidence)")
    sev = str(f.get("severity", "none")).lower()
    passed = sev not in ADVERSE_SEVERITIES
    return _boolean(
        passed,
        "clean" if passed else sev,
        f.get("finding", ""),
        urls=tuple(f.get("source_urls", [])),
    )


def ev_no_criminal(cd: CompanyFinancials) -> CriterionResult:  # LLM-EVIDENCE
    f = _finding(cd, "criminal_record")
    if f is None:
        return _na("not checked (no agent evidence)")
    sev = str(f.get("severity", "none")).lower()
    passed = sev not in ADVERSE_SEVERITIES
    return _boolean(
        passed,
        "clean" if passed else sev,
        f.get("finding", ""),
        urls=tuple(f.get("source_urls", [])),
    )


def ev_insider_trading_healthy(cd: CompanyFinancials) -> CriterionResult:  # CODE
    if cd.insider_max_sold_frac_12mo is None:
        return _na("insider trading data not available")
    v = cd.insider_max_sold_frac_12mo
    cap = TH["insider_sold_frac_max"] * 100
    return _boolean(
        v <= TH["insider_sold_frac_max"],
        f"{v * 100:.0f}% max sold",
        f"max insider sold {v * 100:.0f}% of holdings/12mo (<={cap:g}%)",
    )


def ev_related_party_minimal(cd: CompanyFinancials) -> CriterionResult:  # LLM-EVIDENCE
    f = _finding(cd, "related_party")
    if f is None:
        return _na("not checked (no agent evidence)")
    sev = str(f.get("severity", "none")).lower()
    count = f.get("value")
    passed = sev not in ADVERSE_SEVERITIES and (
        count is None or float(count) <= TH["related_party_count_max"]
    )
    return _boolean(
        passed,
        f.get("finding", "minimal") if passed else sev,
        f.get("finding", ""),
        urls=tuple(f.get("source_urls", [])),
    )


# --- Registry ----------------------------------------------------------------
@dataclass(frozen=True)
class CriterionSpec:
    key: str
    label: str
    weight: float
    provenance: Provenance
    evaluate: Callable[[CompanyFinancials], CriterionResult]


@dataclass(frozen=True)
class DimensionSpec:
    name: str
    nominal_max: float
    criteria: list[CriterionSpec] = field(default_factory=list)

    @property
    def default_weights(self) -> dict[str, float]:
        return {c.key: c.weight for c in self.criteria}


def _c(
    key: str,
    label: str,
    weight: float,
    ev: Callable[..., CriterionResult],
    prov: Provenance = "CODE",
) -> CriterionSpec:
    return CriterionSpec(key, label, weight, prov, ev)


DIMENSIONS: dict[str, DimensionSpec] = {
    "graham": DimensionSpec(
        "Graham Score",
        6.0,
        [
            _c("pe_below_15", "P/E < 15", 0.25, ev_pe),
            _c("pb_below_1_5", "P/B < 1.5", 0.15, ev_pb),
            _c("current_ratio_gt_2", "Current ratio > 2", 0.15, ev_current_ratio),
            _c("de_below_0_5", "D/E < 0.5", 0.25, ev_de),
            _c("positive_eps_5yr", "Positive EPS (5yr)", 0.10, ev_positive_eps),
            _c("earnings_growth_5yr", "EPS growth > 0 (5yr)", 0.10, ev_eps_growth),
        ],
    ),
    "buffett": DimensionSpec(
        "Buffett Quality",
        10.0,
        [
            _c("roe_consistency", "ROE consistency", 0.20, ev_roe_consistency),
            _c("net_margin_trend", "Net margin non-declining", 0.15, ev_net_margin_trend),
            _c("gross_margin_level", "Gross margin strong+stable", 0.15, ev_gross_margin_level),
            _c("de_low_stable", "D/E low & stable", 0.15, ev_de_low_stable),
            _c("fcf_consistency", "FCF positive", 0.20, ev_fcf_consistency),
            _c(
                "revenue_growth_consistency",
                "Revenue grows, no big drop",
                0.15,
                ev_revenue_growth_consistency,
            ),
        ],
    ),
    "munger": DimensionSpec(
        "Munger Composite",
        10.0,
        [
            _c("quality", "Quality (ROE+margin)", 0.50, ev_munger_quality),
            _c("value", "Value (vs sector peers)", 0.30, ev_munger_value),
            _c("capital_efficiency", "Capital efficiency", 0.20, ev_munger_capital_efficiency),
        ],
    ),
    "earnings_quality": DimensionSpec(
        "Earnings Quality",
        10.0,
        [
            _c("ocf_vs_ni", "Cash backs earnings", 0.20, ev_ocf_vs_ni),
            _c("receivables_growth_ok", "Receivables growth ok", 0.15, ev_receivables_growth),
            _c("inventory_growth_ok", "Inventory growth ok", 0.15, ev_inventory_growth),
            _c("margin_stability", "Net margin stable", 0.15, ev_margin_stability),
            _c("goodwill_low", "Goodwill low", 0.15, ev_goodwill_low),
            _c("auditor_stable", "Auditor stable", 0.10, ev_auditor_stable),
            _c("no_nonrecurring_abuse", "One-offs minimal", 0.10, ev_no_nonrecurring_abuse),
        ],
    ),
    "promoter_integrity": DimensionSpec(
        "Promoter Integrity",
        10.0,
        [
            _c("ceo_tenure_ge_5yr", "CEO tenure >= 5yr", 0.15, ev_ceo_tenure, "LLM-EVIDENCE"),
            _c(
                "public_co_experience",
                "Public-co experience",
                0.10,
                ev_public_co_experience,
                "LLM-EVIDENCE",
            ),
            _c("ownership_ge_1pct", "Ownership >= 1%", 0.15, ev_ownership),
            _c(
                "no_sec_enforcement",
                "No SEC enforcement",
                0.20,
                ev_no_sec_enforcement,
                "LLM-EVIDENCE",
            ),
            _c(
                "no_criminal_convictions",
                "No criminal record",
                0.15,
                ev_no_criminal,
                "LLM-EVIDENCE",
            ),
            _c(
                "insider_trading_healthy",
                "Healthy insider trading",
                0.15,
                ev_insider_trading_healthy,
            ),
            _c(
                "related_party_minimal",
                "Related-party minimal",
                0.10,
                ev_related_party_minimal,
                "LLM-EVIDENCE",
            ),
        ],
    ),
}
