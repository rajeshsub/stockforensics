# Migration to Hugging Face Streamlit Space

## Why

The previous architecture used a custom Docker-based Hugging Face Space with:
- Multi-stage build: Node.js for React SPA compilation, Python for FastAPI runtime
- Force-push deployment workflow with orphan branch + git lfs migrate
- Manual port 7860 health-check flipping
- React SPA served by FastAPI (dual build complexity)

The Streamlit SDK approach simplifies this significantly:
- Single Python entry point (streamlit_app.py)
- Hugging Face manages the Streamlit runtime entirely
- No Docker, no Node, no build artifacts
- Clean incremental git pushes (no force-push, no orphan branches)
- Deterministic scoring pipeline (unchanged) used directly without HTTP layer

## What Changed

### Removed

1. **Frontend (React SPA)**
   - `frontend/` directory: React components, Vite config, TypeScript UI code
   - `frontend/dist/`: compiled static assets
   - Archived in `docs/deprecated/` if needed

2. **Build & Deploy Infrastructure**
   - `Dockerfile`: multi-stage Docker build
   - `.dockerignore`: Docker build context filter
   - Force-push deploy workflow (replaced with clean git push)

3. **FastAPI HTTP Layer**
   - `app/core/api.py`: FastAPI app, routes, SSE endpoints, API key middleware
   - `app/main.py`: uvicorn entry point
   - `app/core/scheduler.py`: background scheduler for batch runs
   - HTTP health checks, CORS middleware

### Kept (Unchanged)

All deterministic scoring and pipeline code:
- `app/transform/`: Graham, Buffett, Munger, Earnings Quality, Promoter scoring
- `app/transform/weighted_scorer.py`: core renormalisation engine
- `app/transform/scoring_rules.py`: dimension definitions + criteria
- `app/adapters/`: SEC EDGAR, yfinance, Gemini, Pinecone adapters
- `app/pipeline/analyze.py`: live analysis stream + AI synthesis
- `app/pipeline/runner.py`: batch deterministic scoring
- `app/agent/`: RAG + Gemini-grounded synthesis
- `app/db/`: SQLite schema + repository
- `app/rag/`: SEC filing chunking + embedding

### New

1. **Streamlit Entry Point**
   - `streamlit_app.py`: main Streamlit app at repo root
   - Initializes DB, loads adapters, renders leaderboard + detail views
   - Integrates weight editor, radar charts, AI synthesis streaming
   - No HTTP server; Streamlit framework handles all UI

2. **Dependencies**
   - `requirements.txt`: pinned versions for reproducible Streamlit builds
   - `streamlit`, `plotly` added to `pyproject.toml`
   - `fastapi`, `uvicorn` removed from dependencies

3. **README Front Matter**
   - Changed: `sdk: docker` to `sdk: streamlit`
   - Removed: `app_port: 7860`
   - Added: `app_file: streamlit_app.py`, `sdk_version: 1.41.1`

## Configuration

### Environment Variables (HF Space Secrets)

The Streamlit app reads from `st.secrets`, which maps to Hugging Face Space secrets:

- `GEMINI_API_KEY`: Gemini API key for qualitative synthesis
- `PINECONE_API_KEY`: Pinecone API key for vector search
- `SEC_USER_AGENT`: SEC EDGAR User-Agent header (optional, defaults to placeholder)

Locally, put these in `python/.env` (loaded by pydantic-settings).

### No API Key Middleware

Previously, the FastAPI app checked `X-Api-Key` header/query param against `settings.api_key`.
Streamlit doesn't expose this middleware pattern; the shared password approach was removed.
If access control is needed, use Hugging Face Space's built-in private/gated Space feature instead.

## Testing

### Unit Tests

All existing unit tests remain unchanged and pass:

```bash
cd python && make test
```

Tests call deterministic scoring functions directly (no HTTP mocking needed).

### Smoke Tests

Live adapter tests still work:

```bash
cd python && make smoke
```

### Manual Verification

Run locally:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Verify:
1. Leaderboard renders with 4 deterministic dims
2. Select a company, detail page loads with 5 dimensions, narrative, citations
3. Radar chart renders correctly
4. Weight sliders renormalise scores in real-time
5. "Refresh AI Analysis" streams thinking stages and updates scores

## Deployment

No custom Docker build or force-push workflow.

1. Clone the HF Space repo
2. Copy source files on top (or git add/commit changes)
3. Normal `git push` (no `--force`)

Hugging Face detects `sdk: streamlit` and `app_file: streamlit_app.py` in README front matter,
automatically runs `pip install -r requirements.txt` and `streamlit run streamlit_app.py`.

## Design Principles Preserved

✓ **Deterministic**: All scoring, ratios, red-flag detection stays pure Python, no LLM.
✓ **Educational only**: Never says buy/sell; framed as research.
✓ **Streamed synthesis**: LLM's thinking process visualised as events (now Streamlit progress).
✓ **Live renormalisation**: Weight editor recalculates locally, no server round-trip.
✓ **Offline-friendly**: Seed data allows full browsing without API keys.
