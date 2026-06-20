# StockForensics

Value-investing analysis over the top S&P 500 companies. Computes Graham, Buffett,
Munger, Earnings-Quality and (hybrid) Promoter-Integrity scores **deterministically
in code**; an LLM supplies only qualitative narrative + structured promoter evidence
that code then thresholds. **Never says buy/sell; educational research only.**

Single Python (FastAPI) backend + a static React SPA it serves. See `plan.md` for the
full design and the grilled decision log.

## What the AI does (bounded, live, streamed)

The deterministic scores need no AI. When you **select one stock**, the AI lazily,
live, and up-to-the-minute: (1) RAG-retrieves the SEC filings, (2) writes a narrative,
(3) extracts promoter governance evidence (with Gemini `google_search` grounding for
fresh web/news). Its reasoning **streams** to a "thinking stream" (SSE). Code applies
every threshold and every weighted sum; the LLM never computes a financial figure
(rule #10). Promoter Integrity is finalised live on selection.

## Architecture

```
Python FastAPI (one backend)              React SPA (served by FastAPI)
  transform/  deterministic scoring         5 user-selectable themes
  adapters/   SEC, yfinance, Gemini,        leaderboard (4 deterministic dims)
              Pinecone, iShares (+fixtures) company detail + live thinking stream
  agent/      RAG + grounded synthesis      weight editor (real-time renormalise)
  pipeline/   batch (deterministic) +       radar + breakdowns
              live analyze (streamed)
  db/         SQLite (WAL)
  core/       FastAPI + SSE + scheduler
```

- **Batch** (scheduled/`/api/analysis/run`): computes the 4 deterministic dims for the
  universe → leaderboard. No AI.
- **On selection** (`/api/analyze/{ticker}/stream`): live market refresh + AI, streamed.
- **Market poll** (`/api/market/{ticker}`): every 10s, NYSE-hours gated, 10-min cap,
  valuation-only.

## Run it

```bash
# Backend (offline: works with seed data, no keys)
cd python && make bootstrap          # uv venv, deps, hooks, .env, DB, seed
make test                            # offline gate: 80% coverage, all green
make run-dev                         # FastAPI on :8000

# Frontend
cd ../frontend && npm install && npm run build   # served by FastAPI at :8000
#   ...or `npm run dev` for the Vite dev server on :5173 (proxies /api)
```

Paste keys into `python/.env` when ready (`GEMINI_API_KEY`, `PINECONE_API_KEY`,
`SEC_USER_AGENT`). Missing keys degrade gracefully: deterministic scores + live SEC
data still work; LLM stages skip.

## The 5 scores

| Dimension | Range | Source |
|-----------|-------|--------|
| Graham | 0–6 | SEC EDGAR: 6 valuation/safety criteria (dividend excluded; shown separately) |
| Buffett Quality | 0–10 | SEC EDGAR: ROE/margin/FCF consistency |
| Munger Composite | 0–10 | SEC EDGAR: quality / value / capital efficiency |
| Earnings Quality | 0–10 | SEC EDGAR: cash-vs-earnings, accruals, red flags |
| Promoter Integrity | 0–10 | HYBRID: SEC EDGAR (ownership, insider) + LLM (tenure, SEC, criminal, related-party), code-thresholded |

Every criterion is PASS / FAIL / NA; missing data window-degrades or NA-drops and
weights renormalise. Leaderboard ranks on the 4 deterministic dims (comparable);
the full 5-dim composite appears in a stock's detail view.

## Themes

Five user-selectable themes (Fintech Light, SB Minimal, Slate Pro, Swiss Minimal,
Warm Dashboard) built on CSS design tokens; static mockups in `design-samples/`.

## Tests / CI

Offline fixture suite gates coverage (80%) + CI; live adapters are `make smoke`
(non-gating). `python/`: ruff + black + mypy + bandit, all green.
