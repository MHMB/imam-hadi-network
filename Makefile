# Imam Hadi Network — developer shortcuts
# Run `make help` to list available targets.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# --- variables ---
COMPOSE_DEV := docker compose -f docker-compose.dev.yml
API_DIR := api
WEB_DIR := web
SAMPLE_XLSM := dashboard/sample_data-14050208.xlsm

# --- meta ---
.PHONY: help
help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_.-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- setup ---
.PHONY: setup
setup: db.up api.install web.install ## Bring up dev DB, install api+web deps.

.PHONY: api.install
api.install: ## Install Python deps via uv.
	cd $(API_DIR) && uv sync --all-extras

.PHONY: web.install
web.install: ## Install web deps via pnpm.
	cd $(WEB_DIR) && pnpm install --frozen-lockfile

# --- database (dev only) ---
.PHONY: db.up
db.up: ## Start dev Postgres in background.
	$(COMPOSE_DEV) up -d db
	@echo "Postgres listening on localhost:5434"

.PHONY: db.down
db.down: ## Stop dev Postgres (data persists).
	$(COMPOSE_DEV) stop db

.PHONY: db.reset
db.reset: ## DESTRUCTIVE: drop dev DB volume and recreate.
	$(COMPOSE_DEV) down -v
	$(COMPOSE_DEV) up -d db

.PHONY: db.psql
db.psql: ## Open psql shell against the dev DB.
	$(COMPOSE_DEV) exec db psql -U imamhadi -d imamhadi

# --- migrations ---
.PHONY: db.migrate
db.migrate: ## Apply Alembic migrations to head.
	cd $(API_DIR) && uv run alembic upgrade head

.PHONY: db.makemigration
db.makemigration: ## Generate a new Alembic revision. Usage: make db.makemigration MSG="add foo"
	cd $(API_DIR) && uv run alembic revision --autogenerate -m "$(MSG)"

# --- dev servers ---
.PHONY: api.dev
api.dev: ## Run FastAPI in reload mode on :8000.
	cd $(API_DIR) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: web.dev
web.dev: ## Run Next.js dev server on :3000.
	cd $(WEB_DIR) && pnpm dev

# --- importer ---
.PHONY: import.sample
import.sample: ## Run the importer against the sample xlsm.
	cd $(API_DIR) && uv run python -m app.importer.cli ../$(SAMPLE_XLSM)

# --- quality ---
.PHONY: test
test: api.test web.test ## Run all tests.

.PHONY: api.test
api.test: ## Run Python tests.
	cd $(API_DIR) && uv run pytest

.PHONY: web.test
web.test: ## Run web unit tests.
	cd $(WEB_DIR) && pnpm test

.PHONY: lint
lint: api.lint web.lint ## Lint all sources.

.PHONY: api.lint
api.lint: ## Lint Python (ruff + mypy).
	cd $(API_DIR) && uv run ruff check . && uv run ruff format --check . && uv run mypy src

.PHONY: web.lint
web.lint: ## Lint web (eslint + prettier + typecheck).
	cd $(WEB_DIR) && pnpm lint && pnpm typecheck

.PHONY: fmt
fmt: ## Auto-format all sources.
	cd $(API_DIR) && uv run ruff check --fix . && uv run ruff format .
	cd $(WEB_DIR) && pnpm format

# --- production deploy (filled in during P8) ---
.PHONY: deploy
deploy: ## Pull latest images on prod and restart. Requires `ssh personal` configured.
	@echo "Phase 8 not yet wired. See PLAN.md §8.5."
