"""Map SEC EDGAR companyfacts (XBRL) -> canonical annual series -> CompanyFinancials.

companyfacts shape:
  facts["us-gaap"][CONCEPT]["units"][UNIT] = [{end, val, fy, fp, form, ...}, ...]
We keep annual (form startswith '10-K', fp == 'FY') datapoints, newest unit wins,
and align derived ratios across the fiscal years where their inputs exist (Q9:
gaps just shorten the window)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.adapters.protocols import InsiderSummary, MarketData
from app.transform.models import CompanyFinancials

# Long us-gaap pretax tags split to stay within line length.
PRETAX_TAG = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
    "MinorityInterestAndIncomeLossFromEquityMethodInvestments"
)
PRETAX_TAG_ALT = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxes" "ExtraordinaryItemsNoncontrollingInterest"
)

# canonical field -> us-gaap concept aliases (priority order)
CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "net_income": ["NetIncomeLoss"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "ocf": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "goodwill": ["Goodwill"],
    "inventory": ["InventoryNet"],
    "receivables": ["AccountsReceivableNetCurrent", "AccountsReceivableNet"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "pretax_income": [PRETAX_TAG, PRETAX_TAG_ALT],
}


def _concept_series(facts: dict[str, Any], aliases: list[str]) -> dict[int, float]:
    """Annual {fiscal_year: value} for the first alias that has 10-K/FY data."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for alias in aliases:
        node = gaap.get(alias)
        if not node:
            continue
        best: dict[int, float] = {}
        for points in node.get("units", {}).values():
            annual: dict[int, float] = {}
            for p in points:
                if (
                    p.get("fp") == "FY"
                    and str(p.get("form", "")).startswith("10-K")
                    and p.get("fy") is not None
                    and p.get("val") is not None
                ):
                    annual[int(p["fy"])] = float(p["val"])
            if len(annual) > len(best):
                best = annual
        if best:
            return best
    return {}


def _derived(
    years: list[int], maps: list[dict[int, float]], fn: Callable[..., float | None]
) -> list[float]:
    """Build an oldest->newest series over years where all inputs exist."""
    out: list[float] = []
    for y in years:
        vals = [m.get(y) for m in maps]
        if any(v is None for v in vals):
            continue
        r = fn(*vals)
        if r is not None:
            out.append(r)
    return out


def _latest(m: dict[int, float]) -> float | None:
    return m[max(m)] if m else None


def build_company_financials(
    ticker: str,
    facts: dict[str, Any],
    market: MarketData,
    insider: InsiderSummary,
    *,
    sector: str | None = None,
    sector_pe_percentile: float | None = None,
    sector_pb_percentile: float | None = None,
    sector_peer_count: int = 0,
    promoter_findings: list[dict[str, Any]] | None = None,
    auditor_years: int | None = None,
) -> CompanyFinancials:
    """Assemble a CompanyFinancials from raw companyfacts + market + insider data."""
    s = {k: _concept_series(facts, aliases) for k, aliases in CONCEPTS.items()}
    years = sorted(set().union(*[set(m) for m in s.values()]) if any(s.values()) else set())

    def gm(rev: float, cost: float) -> float | None:
        return (rev - cost) / rev * 100 if rev > 0 else None

    def margin(ni: float, rev: float) -> float | None:
        return ni / rev * 100 if rev > 0 else None

    def roe(ni: float, eq: float) -> float | None:
        return ni / eq * 100 if eq > 0 else None

    def fcf(ocf: float, capex: float) -> float | None:
        return ocf - abs(capex)

    def de(debt: float, eq: float) -> float | None:
        return debt / eq if eq > 0 else None

    eq_latest = _latest(s["equity"])
    debt_latest = _latest(s["long_term_debt"])
    ca, cl = _latest(s["current_assets"]), _latest(s["current_liabilities"])
    current_ratio = ca / cl if ca is not None and cl else market.current_ratio
    debt_to_equity = debt_latest / eq_latest if debt_latest is not None and eq_latest else None

    return CompanyFinancials(
        ticker=ticker,
        sector=sector,
        pe=market.pe,
        pb=market.pb,
        current_ratio=current_ratio,
        market_cap=market.market_cap,
        debt_to_equity=debt_to_equity,
        equity_latest=eq_latest,
        goodwill=_latest(s["goodwill"]),
        total_assets=_latest(s["assets"]),
        eps=[s["eps"][y] for y in years if y in s["eps"]],
        dividends=[s["dividends"][y] for y in years if y in s["dividends"]],
        roe=_derived(years, [s["net_income"], s["equity"]], roe),
        net_margin=_derived(years, [s["net_income"], s["revenue"]], margin),
        gross_margin=_derived(years, [s["revenue"], s["cost_of_revenue"]], gm),
        revenue=[s["revenue"][y] for y in years if y in s["revenue"]],
        fcf=_derived(years, [s["ocf"], s["capex"]], fcf),
        ocf=[s["ocf"][y] for y in years if y in s["ocf"]],
        net_income=[s["net_income"][y] for y in years if y in s["net_income"]],
        capex=[abs(s["capex"][y]) for y in years if y in s["capex"]],
        receivables=[s["receivables"][y] for y in years if y in s["receivables"]],
        inventory=[s["inventory"][y] for y in years if y in s["inventory"]],
        de_series=_derived(years, [s["long_term_debt"], s["equity"]], de),
        pretax_income=[s["pretax_income"][y] for y in years if y in s["pretax_income"]],
        special_items=[],  # not reliably in companyfacts -> NA (Q9)
        auditor_years=auditor_years,
        insider_ownership_pct=insider.ownership_pct,
        insider_max_sold_frac_12mo=insider.max_sold_frac_12mo,
        promoter_findings=promoter_findings or [],
        sector_pe_percentile=sector_pe_percentile,
        sector_pb_percentile=sector_pb_percentile,
        sector_peer_count=sector_peer_count,
    )
