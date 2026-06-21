# StockForensics: single image that builds the React SPA and serves it from the
# FastAPI backend. Built by Hugging Face Spaces (sdk: docker, app_port: 7860).
#
# Build-time secret API_KEY (a Hugging Face Space secret) is baked into the SPA as
# VITE_API_KEY so the served frontend can authenticate against the gated /api/*.
# GEMINI_API_KEY is a *runtime* secret (provisioned by CI) and is never baked in.

# ---- Stage 1: build the SPA ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Bake the gatekeeping key (if the Space defines one) into the bundle at build time.
RUN --mount=type=secret,id=API_KEY,mode=0444,required=false \
    VITE_API_KEY="$(cat /run/secrets/API_KEY 2>/dev/null || echo '')" npm run build

# ---- Stage 2: python runtime serving API + built SPA ----
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv

# Hugging Face runs the container as uid 1000; give it a writable home.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/home/user/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/home/user/app/python/.venv \
    SQLITE_PATH=/home/user/app/data/stockforensics.db

WORKDIR /home/user/app/python
# Deps first (cached layer), then project source.
COPY --chown=user:user python/pyproject.toml python/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY --chown=user:user python/ ./
RUN uv sync --locked --no-dev

# api.py serves ../../../frontend/dist relative to app/core, i.e. /home/user/app/frontend/dist.
COPY --from=frontend --chown=user:user /app/frontend/dist /home/user/app/frontend/dist
RUN mkdir -p /home/user/app/data

# Seed an offline baseline at BUILD time so the DB is ready before the container boots.
# This lets uvicorn bind port 7860 immediately on startup, matching the working Space.
# HF marks the Space "Running" as soon as the port responds, so a slow first-boot seed
# can no longer hold the port closed and leave the Space stuck on "Starting".
# The embedded scheduler (and POST /api/analysis/run) refresh it with live data later.
RUN uv run --no-sync python -m app.db.seed

EXPOSE 7860
CMD ["/home/user/app/python/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
