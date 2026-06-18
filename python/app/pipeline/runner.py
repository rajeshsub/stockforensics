"""ETL + score batch runner (Q4, Q10, Q12). Sequential, checkpointed per company.
Adapters are injected so the same code runs offline (fixtures) or live."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.protocols import InsiderSummary
from app.core.clients import Adapters, build_adapters
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.engine import session_scope
from app.db.models import PipelineRun
from app.db.repository import save_company_score
from app.transform.models import CompanyFinancials
from app.transform.weighted_scorer import score_all
from app.transform.xbrl_map import build_company_financials

log = get_logger("pipeline")


def _attach_sector_context(cds: list[CompanyFinancials]) -> None:
    """Fill sector-relative P/E & P/B percentiles (cheaper = lower) for Munger value."""
    by_sector: dict[str | None, list[CompanyFinancials]] = defaultdict(list)
    for cd in cds:
        by_sector[cd.sector].append(cd)
    for group in by_sector.values():
        n = len(group)
        for cd in group:
            cd.sector_peer_count = n
            for attr, pct_attr in (("pe", "sector_pe_percentile"), ("pb", "sector_pb_percentile")):
                val = getattr(cd, attr)
                peers = [getattr(o, attr) for o in group if getattr(o, attr) is not None]
                if val is None or len(peers) < 2:
                    continue
                cheaper = sum(1 for p in peers if p < val)
                setattr(cd, pct_attr, cheaper / (len(peers) - 1))


def _checkpoint(
    session: Session,
    run_date: datetime,
    ticker: str,
    stage: str,
    status: str,
    detail: str | None = None,
) -> None:
    row = session.execute(
        select(PipelineRun).where(
            PipelineRun.run_date == run_date,
            PipelineRun.ticker == ticker,
            PipelineRun.stage == stage,
        )
    ).scalar_one_or_none()
    if row:
        row.status, row.detail, row.updated_at = status, detail, datetime.now(UTC)
    else:
        session.add(
            PipelineRun(run_date=run_date, ticker=ticker, stage=stage, status=status, detail=detail)
        )


def run_batch(adapters: Adapters, session: Session, *, top_n: int | None = None) -> int:
    """Deterministic-only batch (D18): fetch -> compute the 4 code dims + CODE promoter
    criteria -> store, top-N by market cap. The AI never runs here; the LLM-evidence
    promoter criteria + narrative are filled live on selection (analyze.py)."""
    s = get_settings()
    n = top_n or s.top_n_clamped
    run_date = datetime.now(UTC)

    constituents = adapters.universe.fetch_constituents()
    market = {c.ticker: adapters.market.get_market_data(c.ticker) for c in constituents}
    constituents.sort(key=lambda c: market[c.ticker].market_cap or 0.0, reverse=True)
    selected = constituents[:n]

    cds: list[CompanyFinancials] = []
    meta: dict[str, tuple] = {}
    for c in selected:
        cik = c.cik or adapters.sec.resolve_cik(c.ticker)
        facts = adapters.sec.get_company_facts(cik) if cik else {"facts": {"us-gaap": {}}}
        insider = adapters.sec.get_insider_summary(cik) if cik else InsiderSummary()
        # No promoter_findings in batch -> LLM-evidence promoter criteria evaluate NA.
        cd = build_company_financials(
            c.ticker, facts, market[c.ticker], insider, sector=c.sector, promoter_findings=[]
        )
        cds.append(cd)
        meta[c.ticker] = (c, cik)
        _checkpoint(session, run_date, c.ticker, "extracted", "ok")

    _attach_sector_context(cds)

    for cd in cds:
        dims = score_all(cd)
        c, cik = meta[cd.ticker]
        save_company_score(session, cd, dims, name=c.name, cik=cik, promoter_live=False)
        _checkpoint(session, run_date, cd.ticker, "loaded", "ok")

    session.flush()
    log.info("batch_complete", companies=len(cds))
    return len(cds)


def main() -> None:  # pragma: no cover - CLI entry
    from app.core.logging import configure_logging
    from app.db.migrate import migrate

    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    migrate()
    with session_scope() as session:
        run_batch(build_adapters(s), session)


if __name__ == "__main__":  # pragma: no cover
    main()
