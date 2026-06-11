# Multi-Layout Importer Support — Implementation Plan

Status: **DRAFT for review** (no code written yet).
Source of truth: `real_data.xlsm` (sha `0b6a6293…`), years 1401–1405 + `موضوعات` + `افراد`.

---

## 0. Problem

The current importer only handles two of the five year layouts:

- `year_parser_for()` routes **exactly 1404** to the paired parser; **everything else** to the 1405 table parser.
- Result on `real_data.xlsm`: **1401 + 1402 → 0 loans**, **1403 → garbled**, 1404 + 1405 correct.

Three independent root causes:

1. **Columns differ every year** (loan#, borrower, total, lender, amount all move).
2. **Repayment grid is encoded 3 different ways** across years.
3. **1401–1403 have no topic column**, and the same lender legitimately appears on multiple rows of one loan (dated contributions) — which violates `unique_role_person` and rolls back the whole single-transaction import.

This plan adapts the **code to the file** (the file is authoritative; we do not edit the workbook).

---

## 1. Authoritative layout map

All row/column indices are 1-based (A=1). "paired" = each contribution spans 2 rows; a loan group starts on the row where col A (`ردیف`) holds a literal integer.

| Year | header | data row | step | loan# | channel | liaison | borrower | total | guarantor | lender | amount | balance | grid cols | grid encoding | topic col | extra date cols |
|------|--------|----------|------|-------|---------|---------|----------|-------|-----------|--------|--------|---------|-----------|---------------|-----------|-----------------|
| 1401 | 2 | 3 | 2 | B(2) | C(3) | D(4) | F(6) | E(5) | J(10) | **K(11)** top | **L(12)** bottom | M(13) | P(16)…AM(39) = 24 mo (1401/01→1402/12) | day(top)/amount(bottom) | — none | N=واریز, O=بازگشت, AN, AR, AS, AV=تسویه |
| 1402 | 2 | 3 | 2 | B(2) | C(3) | D(4) | F(6) | E(5) | J(10) | K(11) top | L(12) bottom | M(13) | P(16)…AM(39) = 24 mo (1402/01→1403/12) | day/amount rows | — none | same as 1401 |
| 1403 | 3 | 4 | 2 | B(2) | C(3) | D(4) | E(5) | F(6) | I(9) | **J(10)** top | **K(11)** top | L(12) | M(13)…AL(38) = 26 mo (1403/01→1405/02) | **amount-only (bottom row), no day** | — none | — |
| 1404 | 3 | 4 | 2 | B(2) | C(3) | D(4)=liaison | E(5) | G(7) | — | **L(12)** | **N(14)** top | — | P(16)…AO(41) = 26 mo (1404/01→1406/02) | day/amount rows | H(8) | — |
| 1405 | (table) | 3 | 1 | B(2) | C(3) | E(5) | G(7) | H(8) | F(6) | J(10) | K(11) | L(12) | M(13)+ = 17 mo, 2 cols each | day+amount column-pairs | D(4) | — |

Notes:
- 1401/1402 share one format; 1403, 1404, 1405 each differ.
- The grid amounts per (loan, person) **sum to that person's contribution** (verified: loan 795 صندوق 2 = M1+O1; loan 828 صندوق rows = تیر 3 and تیر 1.7).
- 1401/1402 carry **real Gregorian dates** (`تاریخ واریز` deposit, `بازگشت` return, `تسویه` settled). **Deferred to Phase 2** — Phase 1 uses the persian month-grid for installments (consistent with 1403–1405). Converting Gregorian↔Jalali is out of scope for v1.
- Ignored computed columns everywhere: `مانده` (balance), `امتياز`, `مدت`, `تاخیر`, etc. — the DB recomputes.

---

## 2. Design

### 2.1 Config-driven year engine (replaces the per-year hardcode)

New module `api/src/app/importer/parsers/layout.py`:

```python
class GridEncoding(StrEnum):
    TABLE_PAIRS          = "table_pairs"            # 1405: one row, (day,amount) col pairs
    PAIRED_DAY_AMOUNT    = "paired_day_amount"      # 1401/1402/1404: day top row, amount bottom row
    PAIRED_AMOUNT_ONLY   = "paired_amount_only"     # 1403: amounts on bottom row, no day

@dataclass(frozen=True)
class GridSpec:
    first_col: int
    months: tuple[tuple[int, int], ...]   # explicit (persian_year, month) per column slot
    encoding: GridEncoding

@dataclass(frozen=True)
class YearLayout:
    years: tuple[int, ...]
    header_row: int
    first_data_row: int
    step: int                              # 1 (table) | 2 (paired)
    c_loan: int
    c_borrower: int
    c_total: int
    c_lender: int
    c_amount: int
    amount_row_offset: int                 # 0 = lender row, 1 = next row
    c_topic: int | None                    # None → use DEFAULT_TOPIC
    c_guarantor: int | None
    c_channel: int | None
    c_liaison: int | None
    grid: GridSpec

LAYOUTS: tuple[YearLayout, ...] = ( … 1401, 1402, 1403, 1404, 1405 … )

def layout_for(year: int) -> YearLayout | None: ...
```

New engine `api/src/app/importer/parsers/engine.py`:

```python
def parse_year(ws, persian_year, layout, result) -> None:
    # walk rows by layout.step from first_data_row
    # group start = col A literal int → flush previous, read loan-level fields
    # each contribution row → ParsedParty(role=lender, name=c_lender,
    #     amount=c_amount@amount_row_offset, installments=decode_grid(...))
    # borrower party synthesised once per loan (role=borrower, amount=total)
```

`decode_grid(ws, base_row, layout.grid)` dispatches on `GridEncoding` to the three readers (extracted from today's `year_1404._read_installment_pair` and `year_1405._read_row_installments`).

`parsers/__init__.py::year_parser_for` becomes: look up `layout_for(year)`; if found, return a closure over the engine; else emit an `unknown_layout` error issue (don't crash).

`year_1404.py` / `year_1405.py`: keep their grid-decode helpers (moved/imported by the engine), delete their bespoke row loops. Existing public function names can stay as thin wrappers for back-compat with tests during migration, then removed.

### 2.2 Topic-optional (1401–1403)

These sheets have no topic column. Plan: a module-level `DEFAULT_TOPIC = "نامعلوم"` (already a known legacy topic). When `layout.c_topic is None`, every loan on that sheet gets `topic_name = DEFAULT_TOPIC`; the writer upserts that topic once. **No schema migration** — keeps `loan.topic_id` NOT NULL + FK. (Alternative considered: make `topic_id` nullable — rejected, more invasive, weakens the model.)

### 2.3 Merge repeated lenders (writer)

Confirmed: repeated lender rows are **distinct dated contributions**, not duplicates. Model them as **one party + many installments**.

Change `writer.py::_insert_loans`: before inserting parties, group `parsed_loan.parties` by `(resolved_person_id, role)`:
- `amount` = sum of the group's amounts
- `installments` = concatenation of all the group's installments
- `display_order` = min of the group

One `LoanParty` per (loan, person, role) → `unique_role_person` is satisfied; per-person aggregation stays correct; the dated grid amounts land as that person's installments. No schema change.

### 2.4 Identity / phones

`افراد` has names but no usable phones → all 350 persons fall back to placeholder `+0__name__`. **No change in v1.** Document in the UI/notes that those persons are name-keyed (no contact, no cross-year phone dedup). Optionally collapse the 350 `unknown_phone_format` warnings into one summary issue to cut noise (nice-to-have).

---

## 3. Files touched

| File | Change |
|------|--------|
| `parsers/layout.py` | **new** — `GridEncoding`, `GridSpec`, `YearLayout`, `LAYOUTS`, `layout_for` |
| `parsers/engine.py` | **new** — `parse_year`, `decode_grid` + 3 grid readers |
| `parsers/__init__.py` | `year_parser_for` → config lookup; export engine |
| `parsers/year_1404.py` | reduce to grid-reader helper (or delete after migration) |
| `parsers/year_1405.py` | reduce to grid-reader helper (or delete after migration) |
| `importer/writer.py` | `_insert_loans`: group/merge parties by (person, role); default-topic upsert |
| `importer/runner.py` | `parse_workbook`: unchanged dispatch path, picks up new `year_parser_for` |
| `importer/models.py` | (optional) `ParsedParty`: no change needed; dates deferred |
| `models/enums.py` | (none — reuse existing issue categories; maybe add `unknown_layout`) |

No Alembic migration in v1 (topic-default + merge avoid schema changes).

---

## 4. Test plan

- **Fixtures:** trim `real_data.xlsm` to a tiny per-year sample (or synthesise minimal sheets) under `api/tests/fixtures/`.
- **Unit — layout/engine:** group detection (literal col A), per-year field extraction, each of the 3 grid decoders (day/amount pairing, amount-only, table-pairs), `amount_row_offset`.
- **Unit — writer merge:** a loan with the same lender on 3 rows → 1 party, summed amount, 3 installments; `unique_role_person` not violated.
- **Unit — topic default:** a 1403-style loan (no topic col) → topic `نامعلوم`, loan not skipped.
- **Regression:** 1404 + 1405 parse to the **same** counts as today (golden test on current fixtures) — proves the engine refactor is behaviour-preserving.
- **E2E (host, dry-run):** `--dry-run` on `real_data.xlsm` → assert per-year loan/person/installment counts in expected ranges and **zero** `IntegrityError`.

Acceptance: full `real_data.xlsm` imports in one transaction; loans land for **all five years**; per-year loan counts > 0; no unique-constraint abort.

---

## 5. Rollout

1. Branch `feat/multi-layout-importer` off `main` (carry the uid fix too, or land that PR first).
2. Implement §2; keep 1404/1405 regression-green at every step.
3. Local: `uv run pytest`; then `--dry-run` against a local copy of `real_data.xlsm`.
4. Build + push api image: tag the branch/commit so the `images` CI workflow publishes `ghcr.io/mhmb/imam-hadi-network-api:<tag>`.
5. Deploy: `IMAGE_TAG=<tag> make deploy` (or merge → `latest`), verify `/api/health`.
6. Truncate `import` + `data_issue` (cascades) on prod, then `docker exec imamhadi-api-1 python -m app.importer.cli /uploads/real_data.xlsm`; verify per-year counts.
7. (Optional) HTTP upload smoke test of the dashboard path.

---

## 6. Open questions for review

1. **Merge vs keep-separate** for repeated lenders — plan picks **merge** (§2.3). Confirm. (Earlier you leaned "keep separate"; the dated-contribution finding makes merge cleaner, but keep-separate via dropping the constraint is still viable if you want every deposit as its own row.)
2. **Topic for 1401–1403** = literal `نامعلوم`. OK, or should those loans pull a topic from elsewhere?
3. **1401/1402 real dates** (`تاریخ واریز`/`بازگشت`/`تسویه`) — deferred to Phase 2 (uses month-grid for now). OK?
4. **`موجودی صندوق` / `شاذ` sheets** — currently ignored. Any data needed from them?
5. **Phones** — accept name-keyed persons for now? (No phone data exists in the file.)

---

## 7. Phasing (suggested)

- **P1** — engine + configs for 1404/1405 only, regression-green (pure refactor, no behaviour change).
- **P2** — add 1401/1402/1403 configs + the amount-only grid decoder + topic-default.
- **P3** — writer party-merge.
- **P4** — image build, deploy, prod import + verify.

Each phase is independently testable and shippable.
