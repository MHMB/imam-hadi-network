# API reference

## `openapi.json`

Generated FastAPI OpenAPI 3.1 schema for every read endpoint shipped in
P3.  Used by the Next.js frontend (P4+) to generate typed API client
code via `openapi-typescript`.

Regenerate after any router/schema change::

    cd api
    uv run python scripts/export_openapi.py docs/openapi.json

The CI pipeline does NOT enforce this file is up-to-date — devs
regenerate by hand when responses or paths change.  If the file ever
drifts in production, regenerate from `uv run python -m app.main` and
diff.

## Endpoint summary (P3 scope)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + DB check |
| GET | `/api/version` | App version |
| GET | `/api/kpi` | Dashboard KPI cards + by-year totals |
| GET | `/api/topics` | Loan topic catalog (optional `?year=`) |
| GET | `/api/persons` | Paginated person list (search + flags) |
| GET | `/api/persons/{id}` | Profile (per-year + lifetime + upcoming/overdue) |
| GET | `/api/loans` | Paginated loan list (year/topic/status/borrower/lender/liaison/q) |
| GET | `/api/loans/{id}` | Loan detail (borrowers + lenders + installments) |
| GET | `/api/imports` | Paginated import history |
| GET | `/api/imports/{id}` | One import + full report blob |
| GET | `/api/issues` | DataIssue rows (defaults to latest import) |

Phase 1 is read-only.  `POST /api/imports` (xlsm upload) lands in P6.
