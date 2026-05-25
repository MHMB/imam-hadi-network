# Execution Plan — Phase 1 Build

Companion to [SPEC.md](SPEC.md) and [DESIGN.md](DESIGN.md). This is the engineering plan: ordered phases, concrete tasks, validation gates, risks, parallelization opportunities.

Audience: the engineer(s) building the system.

---

## 0. Target Production Environment (verified)

Single OVH VPS, accessed via `ssh personal`. Inspected live; baseline below is fact, not assumption.

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.3 LTS (`vps-d5fdd1dd`) |
| Hardware | 4 vCPU · 7.6 GiB RAM (6.4 GiB free) · 72 GB disk (63 GB free) · no swap |
| Uptime / load | 178 d / load < 0.2 |
| User | `ubuntu` in `docker`+`sudo` groups (passwordless docker) |
| Public addresses | IPv4 `15.204.95.254` · IPv6 `2604:2dc0:202:300::238b` |
| Default hostname | `vps-d5fdd1dd.vps.ovh.us` (OVH-issued, has DNS, works for ACME) |
| Firewall | `ufw` inactive; assume OVH-edge filtering only |
| Docker | 29.1.2 + Compose v5.0.0 |
| Already-running stack | `n8n` (`:5678` public), `n8n-worker`, `postgres:16` (container-internal only), `redis:6` (container-internal only) on docker network `n8n_default` |
| Ports in use | `:22` (sshd), `:5678` (n8n). **`:80` and `:443` are free.** |
| Reverse proxy installed | **None.** No nginx, no caddy, no traefik. |
| TLS / certs | None. No certbot. |
| Existing app path | `/home/ubuntu/n8n/` (n8n's compose lives here). `/opt/` is empty (only `containerd`). |
| Tooling on host | git 2.43, python 3.12.3, no node, no gh CLI |
| Timezone | UTC |

**Implications baked into the plan below:**
1. **Reuse the host Docker engine; do NOT touch n8n.** Our compose project lives in its own directory, with its own network and volumes. We never share `n8n_default` or n8n's postgres.
2. **Reverse proxy = Caddy** (containerized), not nginx. Reasons: zero-config automatic ACME against the OVH-issued hostname, much smaller compose, no cron renewal job, no certbot install on host. NGINX-vs-Caddy is reversed from earlier DESIGN.md §8 — DESIGN updated accordingly when this plan is executed.
3. **Build images in GitHub Actions → `ghcr.io`; server pulls.** Server has 4 vCPU and limited resources shared with n8n. Building Next.js on it wastes 5–10 min and gigabytes per deploy. CI builds, server pulls, restart is seconds.
4. **Domain.** The default OVH subdomain `vps-d5fdd1dd.vps.ovh.us` is publicly resolvable and works with Let's Encrypt out of the box. If admins have a custom domain (e.g. `dashboard.imamhadi.<tld>`), use that instead; otherwise ship on the OVH subdomain and document a rename procedure. **Open question — ask user.**
5. **App home on server:** `/opt/imamhadi/` (compose, env, uploads, backups). Owned by `ubuntu:ubuntu`. Matches conventional layout, separate from n8n's home-dir install.
6. **Resource budget for the new stack:** ~1.5 GiB RAM, ~1 vCPU steady state. Fits in headroom with n8n; no contention expected.
7. **Backups go to `/opt/imamhadi/backups/`** with 30-day rotation. Disk has 63 GB free — plenty.

---

## 0. Conventions

- **Track A** = backend (Python / FastAPI / Postgres / importer).
- **Track B** = frontend (Next.js).
- **Track C** = infra/devops (Docker, NGINX, deployment).
- A → B → C means strict dependency. A ∥ B means parallel.
- Each phase has an **Exit Gate** — concrete, observable conditions that must hold before moving on. No gate = no merge to `main`.
- "Done" means: code merged, tests green in CI, exit gate verified, demo recorded (screenshot / curl transcript).

Estimates are rough engineer-days for one senior engineer working alone. Halve them if 2 engineers run A and B in parallel.

---

## 1. Critical Path Overview

```
P0 Foundation
   │
   ▼
P1 Schema + Migrations ────────────────────────┐
   │                                            │
   ▼                                            │
P2 Importer (CLI on sample xlsm)                │  parallel: P4 Web Shell starts after P1
   │                                            │
   ▼                                            ▼
P3 API (read endpoints) ◀────── contract ──── P4 Web Shell + i18n
   │                                            │
   ├────────────┬──────────────┐                │
   ▼            ▼              ▼                ▼
P5a KPI/Home  P5b Persons   P5c Loans       (continues)
                │              │
                ▼              ▼
              P5d Person     P5e Loan
              Detail         Detail
                                                ▼
                                            P5f Topics
                                                │
                                                ▼
                                            P6 Admin (upload + status)
                                                │
                                                ▼
                                            P7 Data Quality page
                                                │
                                                ▼
                                            P8 Dockerization + NGINX
                                                │
                                                ▼
                                            P9 Acceptance + Handover
```

Total estimated effort: **≈ 18 – 25 engineer-days** for one engineer, **≈ 12 – 15 days** with one backend + one frontend in parallel from P3 onwards.

---

## Phase 0 — Foundation (½ – 1 day)

**Goal:** repo skeleton, tooling, CI, conventions agreed.

### Tasks
- [ ] Init monorepo with the layout from DESIGN.md §7.
- [ ] `api/`: `pyproject.toml` with FastAPI, SQLAlchemy 2.0, Alembic, openpyxl, pydantic v2, typer, jdatetime, pytest, pytest-asyncio, httpx, ruff, mypy, pre-commit.
- [ ] `web/`: `package.json` with Next.js 15 (App Router, TypeScript), Tailwind, shadcn/ui CLI, dayjs + dayjs-jalali, zod, react-hook-form, recharts, vitest + Playwright.
- [ ] Root `.editorconfig`, `.gitignore`, `LICENSE`, `README.md` (links to SPEC/DESIGN/PLAN).
- [ ] Pre-commit hooks: ruff format/check (Python), prettier + eslint (TS), conventional-commits lint.
- [ ] GitHub repo created under the existing GitHub account. Branch protection on `main`. Required checks: `api-ci`, `web-ci`.
- [ ] GitHub Actions:
  - `api-ci.yml`: install, ruff, mypy, pytest with a temp Postgres service.
  - `web-ci.yml`: pnpm install, lint, typecheck, unit tests, Playwright smoke.
  - `images.yml` (triggers on tag `v*` and on push to `main`): build multi-arch `linux/amd64` images for `api` and `web`, push to **GitHub Container Registry** (`ghcr.io/<owner>/<repo>-api:<sha>` and `:latest` on `main` / `:vX.Y.Z` on tags). Use `docker/build-push-action` with build cache from registry.
  - `images.yml` also pushes a `caddy` image only if we customize Caddyfile-as-image; otherwise we mount the Caddyfile into the official `caddy:2-alpine` image at deploy time.
- [ ] GHCR auth: enable `packages:write` for `GITHUB_TOKEN` in `images.yml`. Server pulls with a personal-access-token-scoped read-only deploy secret stored at `/opt/imamhadi/.env` as `GHCR_TOKEN` (and `docker login ghcr.io -u <user> -p $GHCR_TOKEN` is run once during deploy bootstrap).
- [ ] `docker-compose.dev.yml` providing only Postgres 16 for local dev (separate from `docker-compose.prod.yml`).
- [ ] `Makefile` / `justfile` with `setup`, `db.up`, `db.reset`, `api.dev`, `web.dev`, `import.sample`, plus deploy targets covered in P8.

### Exit gate
- `make setup` from a clean clone produces a runnable dev DB and passing CI.
- All linters pass on empty repo.

### Risks
- Persian/RTL font choice for the web app is irreversible once we ship — pick **Vazirmatn** now and pin a self-hosted copy under `web/public/fonts/` to avoid CDN dependence.

---

## Phase 1 — Schema + Migrations (1 day)

**Goal:** DB schema from DESIGN.md §3 implemented as SQLAlchemy 2.0 models + Alembic migration `0001_init`.

### Tasks
- [ ] Define SQLAlchemy 2.0 ORM models exactly matching DESIGN.md §3.1:
  - `Person`, `PersonGuarantor`, `LoanTopic`, `Loan`, `LoanParty`, `Installment`, `Import`, `DataIssue`.
- [ ] Enums via `CHECK` constraints (not Postgres ENUM types — easier to evolve).
- [ ] Index plan implemented as part of the initial migration (no separate index migration).
- [ ] Enable `pg_trgm` extension; add GIN index on `person.full_name gin_trgm_ops`.
- [ ] Seed migration `0002_seed_topics` inserts the 17 known topics from SPEC.md §2.3 so importer can resolve them on first run.
- [ ] `app/db.py` session factory, `app/config.py` Settings (env-driven).
- [ ] Test: `tests/test_schema.py` — alembic upgrade to head, downgrade to base, upgrade again, no errors. Verify all constraints and indexes are present via `pg_catalog` inspection.

### Exit gate
- `alembic upgrade head` runs clean against a fresh Postgres.
- `pytest tests/test_schema.py` green.
- ER diagram printed via `eralchemy2` matches DESIGN.md §3.2.

### Risks
- `numeric(18,3)` vs `bigint` arithmetic surprises. Pin to numeric throughout to avoid silent rounding when displaying `5.5` million toman.

---

## Phase 2 — Importer CLI (3 – 4 days)

**Goal:** end-to-end parse of `dashboard/sample_data-14050208.xlsm` into the DB with full data-quality report.

This is the **highest-risk** phase. The Excel encoding is non-trivial (row-pair vs column-pair), and getting it wrong corrupts the entire dashboard.

### 2.1 Pure parsing layer (no DB) — ~1.5 days

- [ ] `importer/colors.py` — `is_green(fill) -> bool` (checks fill type, fgColor.rgb, theme fallbacks; case-insensitive on `00B050`).
- [ ] `importer/phone.py` — `canonicalize(raw: str) -> tuple[str, IssueOrNone]`.
- [ ] `importer/models.py` — `ParsedPerson`, `ParsedLoan`, `ParsedParty`, `ParsedInstallment`, `ParsedIssue` (pydantic v2 dataclasses).
- [ ] `importer/parsers/topics.py` — list-of-name parser for sheet `موضوعات`, drops blank/placeholder rows (3 in sample).
- [ ] `importer/parsers/people.py` — reads `افراد` table, emits `ParsedPerson` + deferred guarantor links (by name string). Reports `#REF!` cells as issues without aborting.
- [ ] `importer/parsers/year_1404.py` — row-pair decoder (DESIGN.md §4.3). Tracks current-loan state across IFNA continuation rows. Pairs row `r` (days) with row `r+1` (amounts).
- [ ] `importer/parsers/year_1405.py` — table-row decoder (DESIGN.md §4.4). Groups Table7 rows by `#ش`. Reads month-pair columns (M..AT).
- [ ] `importer/parsers/__init__.py` — `detect_year_sheets(wb) -> list[(year:int, parser)]` dispatcher.
- [ ] Column→month lookup tables for each layout; centralize so 1406 columns aren't off-by-one.

### 2.2 Validation layer — ½ day

- [ ] `importer/validation.py` — runs the rules from DESIGN.md §4.5 against in-memory parsed graph; emits `ParsedIssue`s.
- [ ] Helpful issue messages with Persian summary + English code (so admin sees a human message, ops can grep on code).

### 2.3 DB writer + idempotency — ½ day

- [ ] `importer/writer.py` — opens transaction, performs **per-year scoped replace**: `DELETE FROM installment WHERE contribution.loan.persian_year IN years_in_file` then `DELETE loan_party WHERE ...` then `DELETE loan WHERE ...`. Persons/topics upserted (NOT deleted).
- [ ] Sha-256 of file → `import.source_sha256`. If row with this sha exists in terminal status, short-circuit and return its result (true idempotency).
- [ ] `Import` row lifecycle: `pending → running → success|failed`.
- [ ] `DataIssue` rows linked to the `Import`.

### 2.4 CLI — ½ day

- [ ] `importer/cli.py` (Typer): `python -m importer <file1.xlsm> [<file2.xlsm> ...]`. Sequential processing, exit code = 0 only if all imports `success`.
- [ ] `--dry-run` flag: parse + validate, write nothing, print report.
- [ ] `--report report.json` dumps full DataIssue list.

### 2.5 Tests — ½ – 1 day

- [ ] Fixture: commit `dashboard/sample_data-14050208.xlsm` into `api/tests/fixtures/`.
- [ ] `tests/test_importer_1404.py` — known assertions:
  - 6 topics resolved (or whichever number after filtering blanks).
  - Loan `1500` has 1 borrower party (`نفر 1`, amount=20) and 3 lender parties (`نفر 2`=3, `نفر 3`=7, `نفر 4`=10).
  - Loan `1500` lender `نفر 2` has one installment `1404/06/15` amount=3 status=`paid` (green).
  - Loan `1504` has 5 lender parties with the per-month schedule from SPEC §2.6.
  - Persons `نفر 16 .. نفر 21` whose source cells contain `#REF!` are reported as `broken_ref` issues but do not abort.
- [ ] `tests/test_importer_1405.py` — assertions on `2500`–`2503` from the sample (multi-lender 2502 with 4 lenders summing to 22).
- [ ] `tests/test_idempotency.py` — re-running the importer on the same file:
  - Produces the same DB state (snapshot via `pg_dump --data-only --column-inserts` of the affected tables).
  - Sha-dedup short-circuits the second run (verify by inspecting `import` rows count).
- [ ] `tests/test_per_year_replace.py` — import file A (years 1404, 1405). Then import file B containing only 1405 with modified data. Assert 1404 loans untouched, 1405 loans replaced.
- [ ] `tests/test_validation.py` — synthetic xlsm with deliberately broken totals → expect specific `DataIssue`s emitted.

### Exit gate
- `python -m importer api/tests/fixtures/sample_data-14050208.xlsm` exits 0.
- All assertions above green.
- `pg_dump` of `loan`, `loan_party`, `installment` after import is deterministic across reruns.

### Risks
- **Color detection.** openpyxl may surface theme colors (`theme=...`) instead of `rgb=...`. Build the `is_green` helper to also walk the theme map; sample data uses raw `FF00B050` but real files in the wild may differ.
- **IFNA chains.** Row `r` may reference row `r-2` which itself references `r-4`. Walk the chain or compute eagerly during parse (don't trust openpyxl's formula text alone).
- **Whitespace in person names.** Real Excel data often has trailing spaces or zero-width joiners; normalize on import (NFC + strip).
- **Channel number `0` vs blank.** Normalize both to `NULL` to avoid spurious uniqueness violations.

---

## Phase 3 — API Read Endpoints (2 – 3 days)

**Goal:** every endpoint from DESIGN.md §5 returns the right JSON against the imported sample.

### Tasks
- [ ] `app/schemas/` — pydantic v2 models for every response shape from §5.2. One file per resource.
- [ ] `app/routers/`:
  - [ ] `kpi.py` — `GET /api/kpi` (live SUM/COUNT; cache with `lru_cache(maxsize=1, ttl=60s)` via a small helper).
  - [ ] `persons.py` — list with `q` (pg_trgm) + filters + paging; detail with per-year breakdown.
  - [ ] `loans.py` — list with all the filters; detail returning borrowers[]/lenders[] split.
  - [ ] `topics.py` — list with optional `year`.
  - [ ] `issues.py` — list with filters.
- [ ] `app/services/` — pure query functions; routers stay thin (params parse + service call + response).
- [ ] Pagination helper: `Page[T]` with `items, total, page, page_size`.
- [ ] Filter helpers: `parse_int_list`, `parse_year`, etc.
- [ ] Persian-aware name normalization for `q`: lowercase, strip, replace Arabic ye `ي` → Persian `ی`, Arabic kaf `ك` → Persian `ک`.
- [ ] OpenAPI metadata: tag every endpoint, set Persian summary text (but English `operationId`s and field descriptions).
- [ ] `GET /api/health` returns `{ "db": "ok", "version": "<git sha>" }`.

### Tests
- [ ] `tests/test_api_persons.py` — search for "نفر 1" returns the person; person detail has 1404 breakdown matching SPEC §2.6 expectations.
- [ ] `tests/test_api_loans.py` — list filtered by `year=1404` matches Excel row count; loan `1500` detail shows 1 borrower + 3 lenders.
- [ ] `tests/test_api_kpi.py` — KPI matches manually-computed totals from the sample.
- [ ] `tests/test_api_pagination.py` — page bounds, default page size, max page size enforced.
- [ ] All endpoints have a contract test that loads the response into the pydantic schema (catches drift).

### Exit gate
- Postman/HTTPie collection committed at `api/docs/http/*.http` reproducing every assertion above.
- `curl localhost:8000/api/persons?q=نفر` returns valid JSON in <100ms on dev hardware.
- OpenAPI spec exported as `api/docs/openapi.json` — used as the contract input for Track B.

### Risks
- Concurrent `GET /api/kpi` during an import could see partial data. Wrap the per-year-replace in a single transaction; readers see old-or-new, never half. Test explicitly.

---

## Phase 4 — Web Shell + i18n (1.5 days) *(starts after P1, in parallel with P2/P3)*

**Goal:** Next.js app boots in Persian/RTL with nav, font, design tokens, mock data. No real API yet — placeholder pages.

### Tasks
- [ ] Init Next.js 15 App Router, TypeScript, Tailwind. Configure Tailwind with `rtl` plugin and Persian font as default.
- [ ] `web/src/app/layout.tsx`: `<html dir="rtl" lang="fa">`, `<body class="font-vazirmatn">`, viewport meta, theme color.
- [ ] Self-host Vazirmatn under `web/public/fonts/` and load with `next/font/local`.
- [ ] shadcn/ui init; theme tokens in `tailwind.config.ts` (colors aligned with the brand if any; otherwise neutral palette + a single accent for status `paid`).
- [ ] `web/src/lib/i18n.ts` exporting Persian strings (single map). The DESIGN.md §6.5 glossary becomes the seed file.
- [ ] `web/src/lib/format.ts`:
  - `fmtMoneyMT(n: number)` → `۵٫۵ میلیون تومان`.
  - `fmtMoneyRial(n: number)` → tooltip text.
  - `fmtDateJalali(y: number, m: number, d: number)` → `۱۴۰۴/۰۶/۱۵`.
  - `toPersianDigits(s: string)`.
- [ ] `web/src/lib/api.ts` — typed fetch client generated from `openapi.json` (use `openapi-typescript` + a small `zod` validator at the edge).
- [ ] Layout shell:
  - Desktop: right sidebar (Persian nav: `خانه / افراد / قرض‌ها / موضوعات / مدیریت`).
  - Mobile (<md): bottom tab bar with same items.
  - Header: app title (Persian), settings menu (digit toggle).
- [ ] Placeholder pages for each route returning `در دست ساخت` so navigation is testable.
- [ ] Playwright smoke: load `/`, verify `dir="rtl"`, verify nav has 5 Persian items, verify no English text in DOM (regex `\b[A-Za-z]{4,}\b` should match zero non-attribute text nodes).

### Exit gate
- `pnpm dev` shows Persian-only UI with working RTL navigation on desktop and mobile viewport (Playwright captures both).
- Lighthouse mobile score ≥ 90 for accessibility and best-practices.

### Risks
- Tailwind's logical properties (`ms-`, `me-`, `ps-`, `pe-`) are required everywhere; avoid `ml-`/`mr-` to prevent RTL bugs. Add an eslint rule that forbids the physical variants.

---

## Phase 5 — Web Pages (4 – 6 days)

Build pages in this order to maximize demonstrability — each lands a demoable slice.

### 5a — Home / KPI (½ day)
- [ ] Fetch `GET /api/kpi`. Render 4 stat cards + 2 charts (Recharts: bar chart for loans-by-year, donut for topic distribution).
- [ ] Empty state for an unloaded DB: `هنوز داده‌ای وارد نشده. به بخش مدیریت بروید.`
- [ ] Quick links section: latest 5 imports + top 5 overdue loans.

**Gate:** page renders with seeded sample data; charts show real values.

### 5b — Persons list + search (1 day)
- [ ] Sticky search input (`جستجو در نام، شماره تماس...`).
- [ ] Filter chips: `فقط تأییدشده`، `بدهکار`، `طلبکار`.
- [ ] Mobile: card list. Desktop: table with sortable columns.
- [ ] Pagination via URL query (`?page=2&q=علی`).
- [ ] Debounce search at 250ms.

**Gate:** searching "نفر 1" filters to one row; pagination works at page-size boundaries.

### 5c — Loans list + filter (1 day)
- [ ] Filter drawer (mobile) / sidebar (desktop): year, topic, status (`فعال` / `تسویه‌شده`), liaison autocomplete, borrower typeahead, lender typeahead.
- [ ] Result list with sort options.
- [ ] URL state carries all filters (shareable links).

**Gate:** filter by `سال = ۱۴۰۴` returns 5 loans matching sample; sort by `مانده` (desc) puts unsettled loans on top.

### 5d — Person detail (1 day)
- [ ] Identity card with guarantors as pills.
- [ ] Per-year tabs (mobile: accordion) with as-borrower / as-lender / net.
- [ ] Lifetime totals card.
- [ ] Upcoming / overdue installments tables.

**Gate:** clicking `نفر 2` from the persons list shows their 1404 lender parties on loans `1500`, `1504`; remaining matches Excel.

### 5e — Loan detail (1 day)
- [ ] Header card with totals + status.
- [ ] `قرض‌گیرندگان` section — card list (N-aware, even though Phase 1 = 1).
- [ ] `قرض‌دهندگان` section — one card per lender with installment timeline:
  - Mobile: vertical timeline component (one row per installment, Persian date + amount + status badge).
  - Desktop: month-grid (12 cells per Persian year, colored by status).
- [ ] Footer reconciliation line: `جمع قرض‌گیرندگان: X • جمع قرض‌دهندگان: Y • مبلغ کل: Z`. Red banner if mismatch.

**Gate:** loan `1500` page shows borrower `نفر 1 = 20`, lenders `نفر 2 = 3` (settled), `نفر 3 = 7`, `نفر 4 = 10`, reconciliation OK.

### 5f — Topics (½ day)
- [ ] Year selector + bar chart of totals.
- [ ] List per topic with `count, total, outstanding`; clicking a row navigates to `/loans?topic_id=...&year=...`.

**Gate:** topics page renders the 17 categories; clicking `درمان` filters loans page correctly.

### Cross-cutting for 5a–5f
- [ ] Each page has its own loading skeleton (no flicker).
- [ ] Each list has empty state and error state with retry button.
- [ ] React Query (or TanStack Query) for caching, with 30s `staleTime` and revalidate on focus.
- [ ] Playwright e2e per page hitting a seeded DB.

---

## Phase 6 — Admin Upload + Import Wiring (2 days)

**Goal:** admin uploads `.xlsm` files in the UI and watches the import run.

### 6.1 Backend
- [ ] `POST /api/imports` (multipart, `files[]`): saves each file under `uploads/<sha256>.xlsm`, creates an `Import` row, kicks off `importer.run_import` as a FastAPI `BackgroundTasks` job (acceptable at this scale; revisit if multi-worker).
- [ ] `GET /api/imports?page=` — list with status badges.
- [ ] `GET /api/imports/:id` — detail.
- [ ] `GET /api/imports/:id/issues` — paginated `DataIssue` listing.
- [ ] Concurrency safety: a process-wide `asyncio.Lock` so only one import runs at a time (prevents two admins clicking re-import simultaneously).

### 6.2 Frontend
- [ ] `/admin/import` page:
  - Drop-zone supporting multi-file selection (`.xlsm` only).
  - List of currently-pending uploads with progress bar (just `pending → running → done`).
  - History table with pagination.
- [ ] `/admin/imports/[id]`:
  - Status, duration, years imported, source file name + sha (with copy button).
  - Issues breakdown by severity / category (badge grid).
  - Issues list with filters; each row shows the Persian message + cell reference (`سال 1404!O5`) + copy button so admin can find it in Excel.
- [ ] Auto-poll every 3s while status ∈ {pending, running}; stop on terminal.

### Tests
- [ ] Upload sample file via Playwright; wait until `success`; verify KPI page now shows non-zero numbers.
- [ ] Upload corrupted xlsm; verify status becomes `failed` with `error_message` visible.

### Exit gate
- Admin can go from zero data → fully loaded dashboard using only the web UI (no shell, no CLI).

### Risks
- Large `.xlsm` files (millions of cells) may exceed FastAPI default upload limits and worker timeout. Set `UVICORN_TIMEOUT_KEEP_ALIVE=120`, raise upload size cap to 50 MB, stream to disk rather than buffering in memory.

---

## Phase 7 — Data Quality Page (½ day)

**Goal:** standalone `/admin/issues` page showing the latest import's issues, filter-driven, for daily admin use.

### Tasks
- [ ] Default to `latest import`; allow switching via dropdown.
- [ ] Filter: severity, category, sheet.
- [ ] Click a row → highlight in a side panel showing `context_json` (raw row values that triggered the issue).
- [ ] Empty state: `هیچ ناسازگاری‌ای یافت نشد ✅`.

**Gate:** issues from a deliberately-broken xlsm are listed with correct categories and Persian labels.

---

## Phase 8 — Dockerization & Deployment to OVH (2 – 2.5 days)

**Goal:** one-command production deploy onto the existing OVH VPS without disturbing n8n.

### 8.0 Pre-flight (on the server, ~30 min)

```bash
# Run once, as ubuntu over ssh personal:
sudo mkdir -p /opt/imamhadi/{compose,uploads,backups,traefik}
sudo chown -R ubuntu:ubuntu /opt/imamhadi
mkdir -p /opt/imamhadi/secrets
mkdir -p /opt/imamhadi/traefik/letsencrypt
touch /opt/imamhadi/traefik/letsencrypt/acme.json
chmod 600 /opt/imamhadi/traefik/letsencrypt/acme.json

# Two networks:
# - proxy_net: external, holds Traefik + any service that needs HTTPS ingress.
#              Future services (this project) join this network to be routed.
# - imamhadi_internal: project-internal, holds db ↔ api only (db never reachable externally).
docker network create proxy_net
docker network create imamhadi_internal
```

Sanity checks before any container is started:
- `ss -tlnp | grep -E ':(80|443)\b'` returns **empty** (else nothing to do — investigate first).
- `docker ps` still lists n8n + n8n-worker + postgres + redis (untouched). We never connect them to `proxy_net`.
- `df -h /opt/` shows ≥ 30 GB free.

> n8n stays on `:5678` exactly as today. We do not migrate it. If admins later want it behind Traefik+TLS, that's a separate 5-label change to n8n's compose; **not part of Phase 1.**

### 8.1 Images (built in CI, pulled on server)

- [ ] `api/Dockerfile` — multi-stage:
  - Stage 1: `python:3.12-slim`, install with `uv` or `pip` from `pyproject.toml`.
  - Stage 2: copy app, non-root user, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
  - Entrypoint script runs `alembic upgrade head` before starting uvicorn.
- [ ] `web/Dockerfile` — multi-stage:
  - Stage 1: `node:22-alpine`, `pnpm install --frozen-lockfile`, `pnpm build` (`output: "standalone"`).
  - Stage 2: `node:22-alpine` minimal, copy `.next/standalone` + `public` + `static`, non-root, `CMD ["node", "server.js"]`.
- Both images: `LABEL org.opencontainers.image.source=https://github.com/<owner>/<repo>` so GHCR shows the repo link.
- CI pushes `:latest` (main) and `:vX.Y.Z` (tag) and `:sha-<short>` (every push).

### 8.2 Traefik v3 (reverse proxy + automatic TLS)

Traefik chosen for label-based service discovery. New services added to this project register their routes via docker labels — no Traefik config change required. The project plans multiple containers/aspects beyond imamhadi-dashboard; Traefik scales to that without re-architecture.

#### 8.2.1 Static config — `/opt/imamhadi/traefik/traefik.yml`

```yaml
api:
  dashboard: true
  # dashboard exposed only via the routed Host below, gated by middleware

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
  websecure:
    address: ":443"
    http:
      tls:
        certResolver: le
    http3: {}                  # HTTP/3 (QUIC)

providers:
  docker:
    exposedByDefault: false    # services opt-in via `traefik.enable=true`
    network: proxy_net         # only services on this network are routable
    watch: true

certificatesResolvers:
  le:
    acme:
      email: admin@imamhadi.example      # CHANGE to real contact
      storage: /letsencrypt/acme.json
      # caServer: https://acme-staging-v02.api.letsencrypt.org/directory   # uncomment for first run testing
      httpChallenge:
        entryPoint: web

log:
  level: INFO
accessLog: {}                  # JSON access log to stdout
```

#### 8.2.2 Dynamic config — service labels (in compose, §8.3)

Middleware definitions live as labels on the Traefik service itself so they're versioned with the project, not in a separate dynamic file:

- `imamhadi-auth` → `BasicAuth` (htpasswd line generated by `htpasswd -nbB admin '<password>'`)
- `imamhadi-bodysize` → `Buffering` with `maxRequestBodyBytes=52428800` (50 MB) for `/api/imports`
- `secure-headers` → `Headers` with HSTS, `X-Content-Type-Options=nosniff`, `Referrer-Policy=strict-origin`, `X-Frame-Options=DENY`
- `traefik-dashboard-auth` → separate, stronger basic-auth credentials for the Traefik dashboard at `traefik.<host>`

> Traefik dashboard is gated by **both** basic-auth and (optional) IP allowlist middleware. If you don't need it externally, leave the `traefik.<host>` router off entirely and reach it over an SSH tunnel: `ssh personal -L 8080:traefik:8080` then `curl http://localhost:8080/api/overview`.

### 8.3 Compose file (`/opt/imamhadi/compose/docker-compose.prod.yml`)

```yaml
name: imamhadi

networks:
  proxy_net:
    external: true        # shared edge network; future services join this to be routable
  imamhadi_internal:
    external: true        # project-internal; only db ↔ api

volumes:
  pgdata:

# -- single source of truth for hashes/credentials referenced by labels --
# generated locally:
#   APP_AUTH=$(htpasswd -nbB admin '<dashboard-shared-password>' | sed -e 's/\$/\$\$/g')
#   DASH_AUTH=$(htpasswd -nbB admin '<traefik-dashboard-password>' | sed -e 's/\$/\$\$/g')
# (the sed escapes `$` so docker compose doesn't interpolate it)

services:

  traefik:
    image: traefik:v3.1
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - /opt/imamhadi/traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - /opt/imamhadi/traefik/letsencrypt:/letsencrypt
      - /var/run/docker.sock:/var/run/docker.sock:ro     # discovery only, read-only socket
    networks: [proxy_net]
    labels:
      # --- middleware definitions (applied to other routers via Compose-of-labels) ---
      - "traefik.enable=true"
      - "traefik.http.middlewares.imamhadi-auth.basicauth.users=${APP_AUTH}"
      - "traefik.http.middlewares.imamhadi-bodysize.buffering.maxRequestBodyBytes=52428800"
      - "traefik.http.middlewares.secure-headers.headers.stsSeconds=31536000"
      - "traefik.http.middlewares.secure-headers.headers.stsIncludeSubdomains=true"
      - "traefik.http.middlewares.secure-headers.headers.contentTypeNosniff=true"
      - "traefik.http.middlewares.secure-headers.headers.referrerPolicy=strict-origin"
      - "traefik.http.middlewares.secure-headers.headers.customFrameOptionsValue=DENY"
      - "traefik.http.middlewares.traefik-dashboard-auth.basicauth.users=${DASH_AUTH}"

      # --- optional dashboard router (comment this block out to disable external access) ---
      - "traefik.http.routers.traefik-dashboard.rule=Host(`traefik.${PRIMARY_HOST}`)"
      - "traefik.http.routers.traefik-dashboard.entrypoints=websecure"
      - "traefik.http.routers.traefik-dashboard.tls.certresolver=le"
      - "traefik.http.routers.traefik-dashboard.service=api@internal"
      - "traefik.http.routers.traefik-dashboard.middlewares=traefik-dashboard-auth"

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: imamhadi
      POSTGRES_USER: imamhadi
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks: [imamhadi_internal]        # NOT on proxy_net — db never reachable from edge
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U imamhadi -d imamhadi"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    image: ghcr.io/${GH_OWNER}/${GH_REPO}-api:${IMAGE_TAG:-latest}
    restart: unless-stopped
    depends_on:
      db: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql+psycopg://imamhadi:${DB_PASSWORD}@db:5432/imamhadi
      UPLOAD_DIR: /uploads
      MAX_UPLOAD_MB: "50"
    volumes:
      - /opt/imamhadi/uploads:/uploads
    networks: [proxy_net, imamhadi_internal]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=proxy_net"
      - "traefik.http.routers.imamhadi-api.rule=Host(`${PRIMARY_HOST}`) && PathPrefix(`/api`)"
      - "traefik.http.routers.imamhadi-api.entrypoints=websecure"
      - "traefik.http.routers.imamhadi-api.tls.certresolver=le"
      - "traefik.http.routers.imamhadi-api.middlewares=imamhadi-auth,imamhadi-bodysize,secure-headers"
      - "traefik.http.services.imamhadi-api.loadbalancer.server.port=8000"
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 1g }

  web:
    image: ghcr.io/${GH_OWNER}/${GH_REPO}-web:${IMAGE_TAG:-latest}
    restart: unless-stopped
    depends_on: [api]
    environment:
      NEXT_PUBLIC_API_BASE: /api
    networks: [proxy_net]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=proxy_net"
      - "traefik.http.routers.imamhadi-web.rule=Host(`${PRIMARY_HOST}`)"   # default: matches everything that's not /api
      - "traefik.http.routers.imamhadi-web.priority=1"                     # lower priority than api router (rules ordering)
      - "traefik.http.routers.imamhadi-web.entrypoints=websecure"
      - "traefik.http.routers.imamhadi-web.tls.certresolver=le"
      - "traefik.http.routers.imamhadi-web.middlewares=imamhadi-auth,secure-headers"
      - "traefik.http.services.imamhadi-web.loadbalancer.server.port=3000"
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 1g }

secrets:
  db_password:
    file: /opt/imamhadi/secrets/db_password
```

`.env` (kept on server only, `chmod 600`):
```
GH_OWNER=<github-owner>
GH_REPO=<repo>
IMAGE_TAG=latest
PRIMARY_HOST=vps-d5fdd1dd.vps.ovh.us     # or your custom domain (e.g. dashboard.example.com)
DB_PASSWORD=<long-random>                 # also written to secrets/db_password
GHCR_TOKEN=<read-only PAT>
APP_AUTH=admin:$$2y$$...                  # htpasswd-bcrypt, $ escaped as $$
DASH_AUTH=admin:$$2y$$...                 # separate, stronger credentials for traefik dashboard
```

#### Future services join the platform like this

When the project adds a new container later (e.g. background worker exposing a status page, or an admin-only tool), it joins `proxy_net` and adds the same label pattern — Traefik picks it up automatically, no edits to traefik.yml, no Traefik restart:

```yaml
my-new-service:
  image: ...
  networks: [proxy_net]
  labels:
    - "traefik.enable=true"
    - "traefik.docker.network=proxy_net"
    - "traefik.http.routers.my-svc.rule=Host(`my-svc.${PRIMARY_HOST}`)"
    - "traefik.http.routers.my-svc.entrypoints=websecure"
    - "traefik.http.routers.my-svc.tls.certresolver=le"
    - "traefik.http.routers.my-svc.middlewares=imamhadi-auth,secure-headers"
    - "traefik.http.services.my-svc.loadbalancer.server.port=8080"
```

### 8.4 Backup cron (host crontab, not a sidecar)

```cron
# /etc/cron.d/imamhadi-backup  (owned by root)
0 3 * * * ubuntu docker exec imamhadi-db-1 pg_dump -U imamhadi imamhadi | gzip > /opt/imamhadi/backups/imamhadi-$(date +\%Y\%m\%d).sql.gz && find /opt/imamhadi/backups -name 'imamhadi-*.sql.gz' -mtime +30 -delete
```

### 8.5 Makefile deploy targets

```make
# Local helpers — `make deploy` triggers a deploy via ssh:
deploy:
	ssh personal "cd /opt/imamhadi/compose && \
	  docker login ghcr.io -u $$GH_OWNER -p $$GHCR_TOKEN && \
	  docker compose pull && \
	  docker compose up -d --remove-orphans"

logs:
	ssh personal "cd /opt/imamhadi/compose && docker compose logs -f --tail=200"

ps:
	ssh personal "cd /opt/imamhadi/compose && docker compose ps"

backup-now:
	ssh personal "docker exec imamhadi-db-1 pg_dump -U imamhadi imamhadi | gzip > /opt/imamhadi/backups/imamhadi-manual-$$(date +%Y%m%dT%H%M%S).sql.gz"
```

### 8.6 First-time bootstrap on the server (runbook, ~20 min)

> **Note:** runs once, by hand. After this, every release is just `git tag vX.Y.Z && git push --tags` then `make deploy`.

1. Configure DNS: point your chosen domain at `15.204.95.254` (skip if using `vps-d5fdd1dd.vps.ovh.us`). If you want a Traefik dashboard hostname, add an A record for `traefik.<host>` as well.
2. `scp` (or rsync) the project's `compose/` directory and `traefik/traefik.yml` to `/opt/imamhadi/`.
3. Write `/opt/imamhadi/secrets/db_password` (long random, `chmod 600`).
4. Generate the basic-auth lines on your **laptop** (not on the server — keeps the plaintext password out of shell history on the prod box):
   ```bash
   # App basic-auth (shared password used by admins to log into the dashboard)
   htpasswd -nbB admin '<chosen-app-password>' | sed -e 's/\$/\$\$/g'
   # Traefik dashboard basic-auth (separate, stronger)
   htpasswd -nbB admin '<chosen-dashboard-password>' | sed -e 's/\$/\$\$/g'
   ```
5. Write `/opt/imamhadi/compose/.env` with `GH_OWNER`, `GH_REPO`, `IMAGE_TAG=latest`, `PRIMARY_HOST`, `DB_PASSWORD`, `GHCR_TOKEN`, `APP_AUTH=<output from step 4 line 1>`, `DASH_AUTH=<output from step 4 line 2>`. `chmod 600`.
6. Edit `/opt/imamhadi/traefik/traefik.yml` and set `certificatesResolvers.le.acme.email` to a real address. First time: uncomment the `caServer` line pointing at Let's Encrypt **staging** to avoid hitting prod rate limits while iterating.
7. On the server: `docker login ghcr.io -u <user> -p $GHCR_TOKEN`.
8. `cd /opt/imamhadi/compose && docker compose pull && docker compose up -d`.
9. `docker compose logs -f traefik` until you see a successful certificate exchange (`Obtained certificate ...`). If you used staging in step 6, your browser will warn — that's expected. Once happy, re-comment the staging line and `docker compose restart traefik` to fetch a real cert.
10. From a browser, open `https://<PRIMARY_HOST>/`, enter the shared password, confirm dashboard loads. Open `https://traefik.<PRIMARY_HOST>/dashboard/` to verify Traefik dashboard requires its own credentials.
11. `crontab -e` (as `ubuntu`) installs the backup line from §8.4.

### Tests
- [ ] `docker ps` after deploy shows `imamhadi-traefik-1`, `imamhadi-db-1`, `imamhadi-api-1`, `imamhadi-web-1` **and** the original `n8n_*` containers all healthy.
- [ ] `curl -k -u admin:<pw> https://${PRIMARY_HOST}/api/health` returns `{"db":"ok",...}`.
- [ ] `curl -I https://${PRIMARY_HOST}/api/health` without credentials returns `401`.
- [ ] HTTP→HTTPS redirect: `curl -I http://${PRIMARY_HOST}/` returns `301` to https.
- [ ] n8n at `:5678` still responds normally; n8n's containers were not restarted (compare `docker inspect ... .State.StartedAt`).
- [ ] `docker network inspect proxy_net` shows traefik+api+web; does **not** show any `n8n_*` container.
- [ ] Pulling a newer image tag and `docker compose up -d` restarts only `api`/`web`, not `db`/`traefik`.
- [ ] Reboot the server (`sudo reboot`); after boot, both n8n and imamhadi come back up automatically (`restart: unless-stopped`).
- [ ] `make backup-now` produces a `.sql.gz` ≥ 1 KB.
- [ ] Upload a 30 MB dummy file at `/api/imports` and verify it isn't rejected at the proxy layer (Traefik `Buffering` middleware honors 50 MB cap).

### Exit gate
- A clean tag-and-deploy from a developer laptop puts a new version live in under 5 minutes with zero touches on the server.

### Risks
- **R-deploy-1: n8n collateral damage.** Mitigation: never connect n8n containers to `proxy_net`, never share volumes, never operate on n8n's containers. Smoke-test n8n after every deploy in the runbook.
- **R-deploy-2: ACME rate limits during Traefik iteration.** Let's Encrypt prod ceiling is 5 duplicate certs per week. Mitigation: bootstrap step 6 starts on the staging CA; switch to prod only after a clean cert exchange.
- **R-deploy-3: Docker socket exposure to Traefik.** Traefik needs `/var/run/docker.sock` read-only to do label discovery. Surface: a Traefik RCE could escalate to host root via the docker socket. Mitigation: socket mounted **read-only**, Traefik dashboard gated by separate basic-auth (and optionally only reachable via SSH tunnel — disable the dashboard router for stronger posture). Future-proof option: switch to `tecnativa/docker-socket-proxy` if any concern materializes.
- **R-deploy-4: Label typos silently break routing.** A wrong middleware reference or router rule yields a 404 with no error in Traefik logs by default. Mitigation: enable `accessLog` (done), grep for `404` after deploy in tests, and treat the `traefik-dashboard` page as a routing-source-of-truth check.
- **R-deploy-5: Static-vs-dynamic-config drift.** `traefik.yml` (static) and labels (dynamic) are two configuration surfaces. Mitigation: keep middleware definitions in the Traefik service's own labels (done) so everything routing-related is in one compose file; `traefik.yml` is only entrypoints/providers/ACME.
- **R-deploy-6: Body-size middleware not applied to all upload paths.** The `Buffering` middleware is attached only to the `imamhadi-api` router. Verify per-test that `/api/imports` accepts large bodies and unrelated endpoints don't accidentally allow oversize bodies.
- **R-deploy-7: `proxy_net` accidentally gets too permissive.** Any service joining `proxy_net` becomes discoverable by Traefik (but only routes if `traefik.enable=true` and a `Host(...)` rule). Mitigation: `exposedByDefault: false` (done). Code review the labels on any future service that joins `proxy_net`.
- **R-deploy-8: GHCR private repo + token rotation.** Mitigation: PAT stored only in `/opt/imamhadi/compose/.env`, mode 600, owned by ubuntu. Document rotation as a 60-second runbook entry.
- **R-deploy-9: Host port 5678 (n8n) is publicly exposed without TLS today.** Out of scope for this project. With Traefik already running, putting n8n behind it is a 5-label add to n8n's compose plus joining `proxy_net` — flag as a separate optional task for admins.

---

## Phase 9 — Acceptance + Handover (1 day)

**Goal:** run all acceptance criteria from DESIGN.md §11 end-to-end on a clean install; deliver to admins.

### Tasks
- [ ] Reset the production DB; admins (or you, on their behalf) upload the real xlsm via `/admin/import`.
- [ ] Verify each acceptance bullet (DESIGN.md §11) and capture screenshots.
- [ ] Admin walkthrough: 30-min screen-share covering person search → person profile → loan detail → data quality → re-import.
- [ ] Hand-off doc (`README.md` final): credentials rotation, backup/restore, how to upload a new xlsm, where logs live, who to contact on errors.
- [ ] Tag `v0.1.0`. Cut release notes mapping each Phase to its commits.

### Exit gate
- Admins independently re-import a new xlsm and confirm the dashboard reflects it.
- All Phase 1 acceptance criteria checked.

---

## Cross-cutting Workstreams

### Testing strategy

| Layer | Tool | Coverage target |
|---|---|---|
| Importer | pytest with the real sample as fixture | 100% of public functions; specific assertions per loan in the sample |
| API | pytest + httpx async client | every endpoint, every filter, pagination edges |
| Web unit | vitest | format helpers (money/date/digits), reducers/utils |
| Web e2e | Playwright | one happy path per page + one error/empty state per page |
| Schema | pytest | migration up/down/up + index/constraint inspection |

CI must run all four on every PR. No exceptions for "trivial" doc PRs because docs influence behavior via the i18n map.

### Observability (Phase 1 minimum)

- API: structured JSON logs (request id, path, status, duration). `loguru` or `structlog`.
- Importer: per-file log with file sha, rows parsed, issues by severity, duration.
- `/api/health` + `/api/version` endpoints.
- No Prometheus / Sentry yet — re-evaluate post-Phase-1 if traffic warrants it.

### Persian/RTL guardrails (mandatory)

- Lint rule banning Tailwind physical-direction utilities (`ml-`, `mr-`, `pl-`, `pr-`, `left-`, `right-`); enforce logical (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`).
- Playwright assertion in every page test: no top-level text node matches `\b[A-Za-z]{3,}\b` (catches accidental English leakage).
- Snapshot tests for the i18n map: keys must match a schema (no missing translations, no orphan keys).

### Security (Phase 1 minimum)

- Shared password lives only in the NGINX htpasswd file + `.env`; never in code or git.
- All inbound traffic over TLS in production.
- API CORS limited to the web origin only.
- Pydantic models validate every request body and query param; reject extra fields.
- File upload limited to `.xlsm` mime/extension; reject everything else at NGINX **and** in the API.
- No SQL string concatenation anywhere — SQLAlchemy ORM only.

### Documentation

Each phase updates one of:
- `README.md` — how to run / deploy.
- `SPEC.md` — only on confirmed domain changes.
- `DESIGN.md` — only on architecture changes.
- `PLAN.md` (this file) — check off boxes, add deviations as `### Deviation log` entries.

Never let docs drift behind code. PRs that change behavior must include the doc diff in the same commit.

---

## Risk Register (prioritized)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Real xlsm files differ from sample (extra cols, merged cells, theme colors not `FF00B050`) | High | Medium | Build importer with defensive checks; expose every unrecognized cell as a `data_issue` warning rather than crashing. Test against real (not sample) file **before** Phase 9. |
| R2 | Person duplicates because phone is missing in sample | High | Medium | Importer flags `unresolved_person` issues and creates per-row persons by name only when phone absent; admins resolve later. Future migration merges by phone once collected. |
| R3 | Re-import deletes corrected data | Medium | High | Phase 1 explicitly says Excel is source of truth — no in-DB corrections. Communicate clearly to admins. Add a confirm dialog before re-import. |
| R4 | Multi-borrower in future Excel revisions | Low (Phase 1) | Medium | Schema already N-to-N; parsers structured to accept a `borrowers` block change in one place. |
| R5 | Volume larger than estimated (millions of loans/year as originally floated) | Low | High | Indexes already in place; if KPI page slows past 1s, add a `summary_*` table refreshed at end of import (one-table change, not a redesign). |
| R6 | Persian font CDN outage breaks UI | Low | Low | Self-host fonts; never depend on a CDN. |
| R7 | NGINX Basic Auth credentials shared insecurely | Medium | High | Rotate on every team change. Document the rotation in the handover doc. |
| R8 | `#REF!` and other broken formulas in real data | High | Low | Already designed to surface as `data_issue`; never block import. |
| R9 | Concurrent admin re-imports | Low | Medium | Process-wide `asyncio.Lock` in the importer service (Phase 6). |
| R10 | Browser timezone shifts Jalali dates | Low | Medium | All dates stored and rendered as `(year, month, day)` triples, never as UTC instants. No timezone math. |
| R11 | Co-tenancy with existing n8n stack on the same host (shared docker, shared disk, shared CPU/RAM) | High | High if mishandled | Isolated docker network (`imamhadi_net`), own postgres (no sharing of n8n's DB), own volumes (`pgdata`, `uploads`, `backups`), own compose project name (`imamhadi`). Never run `docker compose down` from a directory outside `/opt/imamhadi/compose`. Smoke-test n8n in the deploy runbook. |
| R12 | Server resource exhaustion under spike (4 vCPU shared with n8n; no swap) | Medium | Medium | Resource limits on `api` and `web` services (`mem_limit: 1g` each, `cpus: "1.0"`). Add swap (`fallocate -l 2G /swapfile`) before going live. Monitor `docker stats` post-launch. |
| R13 | DNS or ACME failure blocks first deploy | Medium | Medium | Use OVH default subdomain on day one (already DNS-correct). Validate ACME on staging endpoint first. |
| R14 | Disk fill from uploaded xlsm + Postgres + backups + n8n logs | Low (63 GB free) | High | 30-day backup retention; rotate Docker logs (`/etc/docker/daemon.json` with `log-opts: max-size=50m, max-file=5`); prune dangling images weekly via cron. |

---

## Deliverables checklist (Phase 1 done = all of these)

- [ ] `api/` — schema, importer (CLI + service), read endpoints, tests, OpenAPI spec.
- [ ] `web/` — Persian/RTL UI with all 8 pages, e2e tests, accessible on mobile and desktop.
- [ ] `nginx/` — TLS + Basic Auth config.
- [ ] `docker-compose.prod.yml` — single-command deploy.
- [ ] `Makefile` — `setup`, `dev`, `import.sample`, `deploy`, `backup`.
- [ ] `README.md` — runbook + handover instructions.
- [ ] `SPEC.md`, `DESIGN.md`, `PLAN.md` — kept current.
- [ ] Acceptance walkthrough recorded + acknowledged by admins.
- [ ] Tagged `v0.1.0` release.

---

## Phase-2 Backlog (out of scope here, captured so we don't forget)

(These are not on the critical path but should be tracked.)

- Per-installment payment-date recording.
- Late-fee / overdue policy logic.
- Per-admin authentication, audit log.
- Asset-type-aware accounting (gold).
- In-app correction UI (replace Excel).
- Notifications/reminders (SMS, email) for upcoming/overdue.
- Public/member self-service portal with restricted views.
- Multi-borrower data entry path once admins start using it.
- PDF/Excel exports.
- Analytics: trend over time, top borrowers/lenders, network graph.
