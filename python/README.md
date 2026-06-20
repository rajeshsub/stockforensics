# StockForensics: Python backend

Deterministic value-investing analysis pipeline. Computes Graham, Buffett, Munger,
Earnings-Quality and (hybrid) Promoter-Integrity scores in code; an LLM supplies
only qualitative narrative + structured promoter evidence that code thresholds.

See the repo-root `plan.md` for the full design and grilled decisions.

## Quick start

```bash
make bootstrap   # uv venv, deps, hooks, .env, SQLite create+migrate, seed (offline)
# paste API keys into .env when ready (GEMINI / PINECONE; SEC_USER_AGENT)
make dev         # backend (:8000) + Vite frontend (:5173) together, hot-reload
make run-dev     # FastAPI on :8000
make run-batch   # one ETL + score batch
make test        # offline gating suite (coverage 80%)
make smoke       # live plumbing checks (non-gating; needs keys)
```

## Layout

- `app/adapters/`: ports (Protocols) + real impls + offline fixtures
- `app/transform/`: ratios, XBRL map, `scoring_rules`, `WeightedScorer`
- `app/rag/`, `app/agent/`: Pinecone RAG + grounded Gemini synthesis (filings + web)
- `app/pipeline/`: universe (iShares), ETL runner, cache, checkpointing
- `app/db/`: SQLite (WAL) models, migrate, seed
- `app/core/`: config, logging, rate-limit, FastAPI app, scheduler
- `tests/unit`: offline (gates coverage); `tests/smoke`: live, non-gating

Deterministic boundary (rule #10): the LLM never computes a financial figure or
sets a financial boolean. Code owns every threshold and weighted sum.
