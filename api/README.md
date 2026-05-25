# imamhadi-api

FastAPI backend for the borrowing-network dashboard.  See top-level
[README.md](../README.md), [DESIGN.md](../DESIGN.md), and
[PLAN.md](../PLAN.md) for context.

## Quick start (dev)

```bash
make db.up                      # bring up Postgres on :5434
cd api
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

OpenAPI: `http://localhost:8000/docs`.

## Tests

```bash
cd api
uv run pytest -q                # 128 tests; integration tests need Postgres
uv run ruff check .             # lint
uv run ruff format --check .    # format
uv run mypy src                 # strict types
```

## CLI importer

```bash
uv run python -m app.importer.cli ../dashboard/sample_data-14050208.xlsm
# --dry-run for parse+validate without DB writes
# --report path/to/report.json for the full outcome JSON
```
