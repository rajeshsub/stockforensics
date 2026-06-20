"""SQLAlchemy 2.0 ORM models. JSON columns hold breakdowns + stored inputs so the
recalc endpoint can rerun the scorer without refetching (Q4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CompanyScore(Base):
    __tablename__ = "company_scores"
    __table_args__ = (UniqueConstraint("ticker", "run_date", name="uq_ticker_run"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String, index=True)
    cik: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    run_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    composite_pct: Mapped[float] = mapped_column(Float, default=0.0, index=True)  # 4-dim (Q22)
    promoter_live: Mapped[bool] = mapped_column(default=False)  # True once live AI ran (Q21)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    # {dim: ScoringDimension.to_dict()}
    scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # CompanyFinancials as dict, for deterministic recalc with new weights
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    narrative: Mapped[str | None] = mapped_column(String, nullable=True)
    promoter_findings: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # live web-grounding citations [{title, url, domain}] for the "In the news" cards
    citations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # AI thinking-stream stages [{stage, message}], replayed on cached views
    thinking: Mapped[list[Any]] = mapped_column(JSON, default=list)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("run_date", "ticker", "stage", name="uq_run_ticker_stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    ticker: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String)  # extracted|scored|synthesized|loaded
    status: Mapped[str] = mapped_column(String)  # ok|skipped|error
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class LlmCache(Base):
    __tablename__ = "llm_cache"
    cache_key: Mapped[str] = mapped_column(String, primary_key=True)  # ticker|accession|prompt_ver
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    chunk_hash: Mapped[str] = mapped_column(String, primary_key=True)
    vector: Mapped[list[float]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
