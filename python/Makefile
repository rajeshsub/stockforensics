.DEFAULT_GOAL := help
SHELL := /bin/bash

# On Windows the bare `npm` resolves to an extensionless launcher that Git Bash
# cannot exec ("No such file or directory"); the .cmd shim is the one that runs.
ifeq ($(OS),Windows_NT)
NPM := npm.cmd
else
NPM := npm
endif

.PHONY: help bootstrap dev run-dev run-batch test smoke lint typecheck security refresh-universe clean

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

bootstrap: ## One-step offline setup: venv, deps, hooks, .env, DB, seed
	uv sync
	uv run pre-commit install
	[ -f .env ] || cp .env.example .env
	uv run python -m app.db.migrate
	uv run python -m app.db.seed
	@echo "Bootstrap complete. Paste API keys into .env, then 'make run-batch'."

dev: ## Start backend (:8000) + frontend (:5173) with hot reload
	@[ -d ../frontend/node_modules ] || (cd ../frontend && $(NPM) install)
	@trap 'kill 0' EXIT; \
	uv run uvicorn app.main:app --reload --port 8000 & \
	(cd ../frontend && $(NPM) run dev) & \
	wait

run-dev: ## Run FastAPI (uvicorn) on :8000
	uv run uvicorn app.main:app --reload --port 8000

run-batch: ## Run one ETL+score batch
	uv run python -m app.pipeline.runner

test: ## Offline gating test suite (coverage 80%)
	uv run pytest

smoke: ## Live plumbing+shape checks (non-gating); needs keys
	uv run pytest -m smoke --no-cov

lint: ## ruff + black --check
	uv run ruff check app tests
	uv run black --check app tests

typecheck: ## mypy
	uv run mypy app

security: ## bandit
	uv run bandit -q -r app

refresh-universe: ## Force-pull iShares IVV constituents snapshot
	uv run python -m app.pipeline.universe --refresh

clean: ## Remove generated artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage data/stockforensics.db
