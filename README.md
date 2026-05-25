# Imam Hadi Network — Dashboard

Read-only Persian/RTL dashboard for a community-run interest-free borrowing network. Migrates the legacy Excel workbook to a relational database and surfaces per-person and per-loan views.

## Documents

- **[SPEC.md](SPEC.md)** — domain model from analysis of the legacy `.xlsm`.
- **[DESIGN.md](DESIGN.md)** — architecture, schema, API, UI design.
- **[PLAN.md](PLAN.md)** — phased execution plan and runbook.

## Repository layout

```
api/                    Python / FastAPI / SQLAlchemy / Alembic / Importer
web/                    Next.js (App Router, TypeScript, RTL)
dashboard/              Sample legacy xlsm
docker-compose.dev.yml  Local Postgres for development
docker-compose.prod.yml Production stack (Traefik + api + web + db)  -- added in P8
.github/workflows/      CI: api-ci, web-ci, images
Makefile                Developer shortcuts
```

## Quick start (development)

```bash
# Prereqs: docker, uv (https://docs.astral.sh/uv/), pnpm, make
make setup           # bring up local Postgres + install deps
make api.dev         # start FastAPI on :8000
make web.dev         # start Next.js on :3000 (separate terminal)
make import.sample   # run importer against dashboard/sample_data-14050208.xlsm
make test            # run all tests
```

## Production

See [PLAN.md §Phase 8](PLAN.md) for the OVH bootstrap runbook.

## License

MIT — see [LICENSE](LICENSE).
