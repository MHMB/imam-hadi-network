# System Specification — Borrowing Network (Imam Hadi Network)

## 1. Overview

A community-run interest-free borrowing network. Members borrow money (and occasionally gold) from one or more other members of the network and repay in single or multiple scheduled installments without commission or interest. Today the entire system is operated through a macro-enabled Excel workbook (`.xlsm`). Goal:

- **Phase 1 (this work):** Read-only web dashboard.
  - Migration script: parse the existing Excel into a relational database.
  - Web app: per-person view, per-loan view, summaries by year/topic. No write operations.
- **Phase 2 (future, out of scope here):** Replace Excel as the system of record with full CRUD, payment recording, late-fee tracking, approvals, asset-aware accounting, etc.

Source artifact analyzed: `dashboard/sample_data-14050208.xlsm` (sample data; real names redacted to `نفر 1`, `نفر 2`, ...). Persian (Jalali) calendar throughout. Years observed: 1404, 1405.

---

## 2. Source Workbook Structure

### 2.1 Sheets

| Sheet (Persian) | English | Role |
|---|---|---|
| `سال 1404` | Year 1404 | Loan ledger for year 1404 (legacy 2-row-per-lender layout) |
| `سال 1405` | Year 1405 | Loan ledger for year 1405 (cleaner 1-row-per-lender layout, native Excel Table) |
| `موضوعات` | Topics | Catalog of loan purposes/categories with per-category totals |
| `افراد` | People | Master person registry with guarantors and rolled-up balances |

VBA: one user-defined function `SumifColor(ColorRange, CellColor, SumRange)` in `Module1.bas` — sums values in `SumRange` whose corresponding `ColorRange` cell matches `CellColor.Interior.ColorIndex`. Used to total **green-shaded paid installments**.

### 2.2 People sheet (`افراد`, table `person`, range `B2:N23`)

Columns:

| # | Header (Persian) | Meaning | Notes |
|---|---|---|---|
| 1 | نام و نام خانوادگی | Full name | Primary key (matched by `VLOOKUP` and `SUMIFS` from year sheets) |
| 2 | شماره تماس | Phone | |
| 3 | پیامرسان | Messenger / IM handle | |
| 4 | رابط/ضامن-4 | Liaison/Guarantor 4 | Free-text, references another person's name |
| 5 | رابط/ضامن-3 | Liaison/Guarantor 3 | |
| 6 | رابط/ضامن-2 | Liaison/Guarantor 2 | |
| 7 | رابط/ضامن-اصلی | Main liaison/guarantor | Often blank |
| 8 | تایید | Approved | `1` = approved, blank = pending |
| 9 | مقدار قرض داده شده | Total amount lent | `SUMIFS` over year-1404 amount col by lender name |
| 10 | مانده طلبکاری | Outstanding receivable | `SUMIFS` over year-1404 remaining col by lender name |
| 11 | مجموع قرض گرفته شده | Total amount borrowed | `SUMIFS` by borrower name |
| 12 | مانده بدهی | Outstanding debt | `SUMIFS` over remaining col by borrower name |
| 13 | سرمایه نزد صندوق | Capital with fund | `= مانده طلبکاری − مانده بدهی` (net position) |

Caveats:
- Roll-up formulas only consume `سال 1404`. Year 1405 contributions are **not** aggregated into the person sheet.
- Several rows have broken/`#REF!` formulas (rows 16–23) — formula corruption from row inserts/deletes.
- Guarantor cells reference other persons by **name string**, not ID — fragile to renames.

### 2.3 Topics sheet (`موضوعات`, table `titles`, range `A2:C22`)

| # | Header | Meaning |
|---|---|---|
| 1 | num | Numeric tag (only `0` is set, for "unknown") |
| 2 | موضوعات | Topic name (FK target for the year sheet `موضوع` column) |
| 3 | مجموع | Sum of loan totals in that topic — **only for year 1404** |

Observed topics (17 active + 3 empty placeholder rows):

```
از کار افتادگی (disability), ازدواج (marriage), آموزشی (education),
بدهی (debt), تولد فرزند (childbirth), خانه (housing), درمان (medical),
زیارت (pilgrimage), عتبات (holy shrines), کار فرهنگی (cultural work),
کالای دیجیتال (digital goods), کسب و کار (business), نامعلوم (unknown),
وسیله نقلیه (vehicle), امور جاری (current affairs), وام (loan),
سرمایه گذاری (investment)
```

Data validation on the year sheets restricts the topic column to `موضوعات!$B$3:$B$22`.

### 2.4 Year-1404 sheet (`سال 1404`, range `A1:AO31`)

Header rows 1–3 (row 3 is the field header). Data rows start at row 4. Two physical rows make one logical "lender installment row" (see §2.6).

Columns A–O (loan + per-lender ledger):

| Col | Header | Meaning |
|---|---|---|
| A | ردیف | Row index (only on first row of a loan) |
| B | ش | Loan number (e.g. 1500, 1501, ...). Inherited via `IFNA(prev, this)` for continuation rows |
| C | ش.کانال | Channel number (cross-network identifier; nullable) |
| D | رابط | Liaison label (free text: `سید`, `روابط`, ...) |
| E | قرض گیرنده | Borrower (person name) |
| F | سرمایه | Borrower's fund-capital lookup (`VLOOKUP` into `person`) |
| G | مجموع | Loan total amount (only on first row of loan) |
| H | موضوع | Topic (validated against topics list) |
| I | توضیحات | Free-text description |
| J | ش ر | Unused (all blank in sample) |
| K | ضامن | Per-loan guarantor (all blank in sample — guarantor lives on person sheet for 1404) |
| L | خیر | Lender ("خَیِّر" = benefactor); person name |
| M | سرمایه | Lender's fund-capital lookup |
| N | مبلغ | Amount lent by **this** lender to this loan |
| O | مانده | Remaining (unpaid) for this lender, computed as `=N − SumifColor(P{r+1}:AM{r+1}, $N$3, P{r+1}:AM{r+1})` — i.e. lent minus sum of green-shaded installment amounts |

Columns P–AO: 26 monthly cells covering **Farvardin 1404 → Ordibehesht 1406**:

```
P=Farvardin04, Q=Ordibehesht04, ..., AA=Esfand04,
AB=Farvardin05, ..., AM=Esfand05,
AN=Farvardin06, AO=Ordibehesht06
```

The month range `P3:AO31` is wrapped in Excel table `Table4` but only for formatting — the table has no data row alignment.

### 2.5 Year-1405 sheet (`سال 1405`, table `Table7`, range `A2:AT11`)

Cleaner layout — **one row per lender** and **two columns per month** (day + amount). Loan info is replicated across lender rows via `=A{first_row}` formulas (so each row is a self-contained record for filtering).

Loan + lender columns (A–L):

| Col | Header | Meaning |
|---|---|---|
| A | ردیف | Row index |
| B | #ش | Loan number (e.g. 2500, 2501, ...) |
| C | #شماره | Channel number |
| D | موضوع | Topic |
| E | رابط | Liaison label |
| F | ضامن | Per-loan guarantor (now populated, e.g. `نفر 20`) |
| G | قرض گیرنده | Borrower |
| H | مجموع | Loan total |
| I | توضیح | Description |
| J | قرض دهنده | Lender |
| K | مبلغ | Amount lent by this lender |
| L | مانده | Remaining = `[مبلغ] − SumifColor([1]:[12], $J$1, [1]:[12])` |

Columns M–AT: 17 month-pairs covering **Farvardin 1405 → Mordad 1406**:

```
(M=Farvardin day, N=Farvardin amount), (O=Ordibehesht day, P=amount), ...,
ending with (..., AS=Mordad06 day, AT=amount)
```

Header row 2 alternates month-name / numeric-index (the numeric index `1..17` is the Excel-table column name used in the structured `SumifColor` formula).

### 2.6 The "row-pair / column-pair" installment encoding

This is the workbook's most non-obvious feature.

**Year 1404 (column-major, 2 rows per lender):**
- For each lender on a loan, Excel uses two adjacent rows.
- Top row (loan/info row): under each month column, stores the **day of the month** the installment is due.
- Bottom row: stores the **installment amount** for that same month.
- Sum of bottom-row amounts across months = amount lent by that lender (col N).
- Cells shaded green (`#00B050`) on the bottom row = **paid**. The `مانده` formula sums green amounts and subtracts from total.

Example — loan 1500, lender نفر 2 lent 3:
- Row 4, col `شهریور04` = `15` → installment due day 15 of Shahrivar 1404
- Row 5, col `شهریور04` = `3` (green) → 3 units paid on that date → fully repaid

**Year 1405 (row-major, 2 columns per lender row):**
- Each lender = one row.
- Per month: left column = day, right column = amount.
- Same green-shading convention for paid installments.

**Implications for migration:**
- The "row-pair" encoding in 1404 must be unfolded by reading row `r` (day) paired with row `r+1` (amount) for every loan.
- Cell fill color must be read alongside cell value to determine paid status.
- Loan boundaries in 1404 are inferred from non-blank `ردیف`/`ش`/`مجموع` cells — continuation rows use `IFNA` formulas that resolve to the same loan number when computed.

---

## 3. Domain Model (target relational schema)

### 3.1 Entities

#### `Person`
- `id` (PK)
- `full_name` (unique, indexed) — current de-facto key in Excel
- `phone` (nullable)
- `messenger` (nullable)
- `is_approved` (bool, default false) — maps to `تایید`
- `created_at`, `updated_at`

#### `PersonGuarantor`  *(many-to-many self-link with role/order)*
- `person_id` (FK Person)
- `guarantor_id` (FK Person)
- `role` enum: `main`, `secondary_2`, `secondary_3`, `secondary_4` (4 ordered slots in Excel)

> Note: in Excel these are name strings, frequently blank. Migrator must resolve names → IDs and tolerate orphans (unmatched names → log + skip).

#### `LoanTopic`
- `id`
- `legacy_num` (nullable int) — corresponds to `موضوعات.num` (only `0` set in sample)
- `name` (unique)

Seed list = the 17 names listed in §2.3.

#### `Loan`
- `id`
- `loan_number` (string/int, unique within year) — `ش` / `#ش`
- `channel_number` (nullable) — `ش.کانال`
- `persian_year` (smallint: 1404, 1405, ...)
- `borrower_id` (FK Person)
- `guarantor_id` (FK Person, nullable) — per-loan guarantor (1405 only, blank for 1404)
- `liaison_label` (string, nullable) — `سید`, `روابط`, free text. Could be normalized into a `Liaison` enum/table later.
- `topic_id` (FK LoanTopic)
- `total_amount` (decimal)
- `asset_type` enum: `cash`, `gold` (default `cash`) — **new field**, not present in Excel; admins say network supports gold. All migrated rows default to `cash` until disambiguated.
- `description` (text, nullable)
- `created_at`

**Invariant:** `total_amount = SUM(LoanContribution.amount WHERE loan_id = this)`. Migrator should validate and flag mismatches.

#### `LoanContribution`  *(one lender's part of a loan)*
- `id`
- `loan_id` (FK Loan)
- `lender_id` (FK Person)
- `amount` (decimal)
- `display_order` (int) — preserves Excel ordering

#### `Installment`  *(one scheduled repayment of one contribution)*
- `id`
- `contribution_id` (FK LoanContribution)
- `due_persian_year` (smallint)
- `due_persian_month` (smallint, 1–12)
- `due_day_of_month` (smallint, 1–31)
- `amount` (decimal)
- `status` enum: `paid`, `unpaid` — derived from green fill at migration time
- `paid_persian_date` (date, nullable) — **not captured in Excel today**; reserved for Phase 2
- `notes` (nullable)

**Invariant:** `LoanContribution.amount = SUM(Installment.amount WHERE contribution_id = this)`. Migrator should validate.

### 3.2 Derived views (for the dashboard)

These are read-only projections — implement as SQL views or query helpers, do not denormalize at write time.

- `v_person_summary` per person:
  - `total_lent` = Σ `LoanContribution.amount` where `lender_id = person`
  - `outstanding_receivable` = Σ unpaid installment amounts where `lender_id = person`
  - `total_borrowed` = Σ `Loan.total_amount` where `borrower_id = person`
  - `outstanding_debt` = Σ unpaid installment amounts where loan's `borrower_id = person`
  - `net_capital` = `outstanding_receivable − outstanding_debt`

- `v_loan_summary` per loan:
  - `total_amount`, `total_paid`, `total_remaining`, `lender_count`, `installment_count`, `next_due_date`, `is_settled` (`total_remaining == 0`).

- `v_topic_summary` per topic per year:
  - count of loans, sum of total amounts, sum outstanding.

- `v_overdue_installments`:
  - all unpaid installments where `due_persian_date < today_jalali()`.
  - Excel does not surface this; the dashboard should.

---

## 4. Migration Script (Phase 1, deliverable)

### 4.1 Inputs / outputs
- Input: an `.xlsm` file matching the layout above. Path passed via CLI arg.
- Output: rows written into the relational DB (Postgres preferred; SQLite acceptable for first iteration). Idempotent: re-runs should produce the same DB state for the same input.

### 4.2 Algorithm

1. **Open workbook** with `openpyxl(data_only=False, keep_vba=True)`.
2. **Load topics** from `موضوعات!B3:B22` → upsert into `LoanTopic`.
3. **Load people** from `افراد` table:
   - Insert `Person` rows for each non-blank name.
   - Defer guarantor links to a second pass (after all persons exist), then insert `PersonGuarantor`.
   - Build a `name → person_id` map for the year-sheet pass.
4. **Parse year sheets** (one per detected `سال NNNN` sheet):

   **Common preprocessing per row:**
   - Read both the cell value and `cell.fill.fgColor.rgb` for month columns.
   - Treat `#00B050` (case-insensitive, ARGB form `FF00B050`) as the "paid" sentinel.

   **Year 1404 parser (2-rows-per-lender, column-major months):**
   - Iterate row-by-row from row 4. Track `current_loan` whenever a non-blank `ردیف`/`ش`/`مجموع` is seen.
   - For each lender row `r`:
     - Loan-level fields (`ش`, `قرض گیرنده`, `مجموع`, `موضوع`, ...) are taken from the most recent non-blank values, resolving `IFNA` chains by carrying forward the last seen literal.
     - Lender + amount: cols `L`, `N` of row `r`.
     - Months: for each column `c` in `P..AO`:
       - `day = ws.cell(r, c).value`
       - `amount_cell = ws.cell(r+1, c)` → `amount = amount_cell.value`, `paid = is_green(amount_cell)`
       - Skip if both `day` and `amount` are blank.
       - Map column index → `(persian_year, persian_month)` using the fixed sequence Farvardin04..Ordibehesht06.
   - Increment `r` by 2 to move to next lender.
   - At the end of each loan group (next non-blank `ردیف`), commit the loan.

   **Year 1405 parser (1-row-per-lender, row-major month-pairs):**
   - Iterate over `Table7` rows.
   - Loan-level fields are present in every row (replicated via `=A{first}` formulas), so just read them directly per row.
   - Group rows by `#ش` (loan number) to build the `Loan` and its `LoanContribution`s.
   - Months: walk columns `M..AT` in pairs `(day_col, amount_col)`. The header row defines mapping (Farvardin → 1, …, Mordad06 → 17). Translate to `(persian_year, persian_month)` via the same lookup table.
   - Paid flag is read from the `amount_col` cell's fill color.

5. **Validate invariants** (warn, do not abort):
   - Loan total = Σ contribution amounts.
   - Contribution amount = Σ installment amounts.
   - Borrower / lender / guarantor names resolve to known persons.
   - Topic name is in catalog.

6. **Write a migration report** (`migration_report.json` or stdout): row-by-row warnings, unresolved names, mismatched totals, blank/orphan rows, broken formulas (e.g. `#REF!` cases observed in `افراد` rows 16–23).

### 4.3 Edge cases to handle (observed in sample)

- `#REF!` formulas in `افراد!J16:J23` — totals must be recomputed in DB, not read from Excel.
- Empty placeholder topic rows (`موضوعات` rows 20–22 with formulas but no name) — skip.
- Continuation rows with only `=IFNA(B{r-2},B{r})` — must dereference to literal loan number.
- Person names with leading/trailing whitespace — normalize on import.
- Multiple loans by the same borrower in the same year — keep distinct via `(persian_year, loan_number)`.
- Channel number `0` vs blank — normalize both to NULL.
- Liaison column free-text variants — preserve verbatim, do not enforce.

### 4.4 Technology suggestion (not binding)

- Python 3.11+, `openpyxl` for parsing, `SQLAlchemy` 2.0 + Alembic for schema, Postgres in prod / SQLite in dev. CLI via `typer`.

---

## 5. Web Dashboard (Phase 1, deliverable)

### 5.1 Scope

Read-only. No login flow defined yet (defer to deployment env / reverse proxy auth, or trivial shared password). Persian/RTL UI is mandatory — admins are Persian speakers and the data is Persian.

### 5.2 Pages

1. **Home / Overview**
   - Top-level KPIs: total active loans, total outstanding, total people, count of overdue installments.
   - Year selector (1404 / 1405 / All).
   - Topic distribution chart.

2. **People list / search**
   - Search by name (Persian, prefix + substring + simple normalization for Arabic ye/kaf vs Persian).
   - Table: name, phone, total lent, total borrowed, net capital, approval status.

3. **Person detail** (the primary admin use case)
   - Header: name, phone, messenger, approval, guarantors (linked).
   - "As borrower" section: list of their loans with total, paid, remaining, status, next due date. Click → loan detail.
   - "As lender" section: list of contributions with total, paid, remaining, schedule. Click → loan detail.
   - "Net position" card: receivable, debt, net capital.
   - Upcoming/overdue installments table (across both roles).

4. **Loans list**
   - Filter by year, topic, status (active / settled), liaison, borrower, lender.
   - Table: loan #, year, borrower, topic, total, lenders, paid, remaining, status.

5. **Loan detail**
   - Loan-level info.
   - Contributions table (one row per lender).
   - For each contribution, expandable installment schedule with paid/unpaid badges and per-installment due date.

6. **Topics**
   - List + per-topic summary (count, total, outstanding) per year.

### 5.3 Non-functional

- Persian (Jalali) date formatting throughout. Use a Jalali date library (e.g. `jdatetime` server-side, `moment-jalaali`/`dayjs-jalali` client-side).
- RTL layout, Persian numerals optional (toggle in settings).
- No write endpoints. Mutations return `405`.
- Pagination on all list views (default 50, max 500).

### 5.4 Stack suggestion (not binding)

Backend: FastAPI + SQLAlchemy. Frontend: a small React (Next.js) app or server-rendered Jinja templates if the team prefers minimal JS. Charts: Recharts or Chart.js.

---

## 6. Known Gaps / Issues in Excel (from admins + observed)

These are documented for Phase 2; **the Phase 1 dashboard does not need to fix them**, only surface them.

1. **Actual payment dates not recorded.** Only the *scheduled* installment date is stored. Whether a payment was on time, early, or late is invisible — only "paid yes/no" via cell color.
2. **Late-payment tracking absent.** No delinquency flags, days-late, or follow-up workflow.
3. **Topic totals only computed for 1404.** `موضوعات!C` formulas reference `سال 1404!G$4:G$31` only; new years are not aggregated.
4. **Person rollups only consume 1404.** Same root cause — formulas hardcoded to `سال 1404`. Year 1405 contributions don't appear in any person's summary.
5. **Broken formulas** in `افراد` rows 16–23 (`#REF!`) from prior row insert/delete.
6. **Color-coded state** is fragile (Excel formatting can be wiped accidentally; no audit trail of who marked something paid and when).
7. **Names as keys.** Renaming a person silently breaks `VLOOKUP`/`SUMIFS` references everywhere.
8. **Asset type (cash vs gold) not modeled.** Admins note that loans can be in gold; current Excel has no column for it — gold loans are presumably tracked off-sheet or in description text.
9. **No guarantor on 1404 loans.** The 1404 sheet has a `ضامن` column but it is unused; guarantors are read from the person record. 1405 records guarantor per-loan, which is more correct.
10. **Channel number semantics undocumented.** Some loans have a `ش.کانال` (e.g. `901`, `902`), some don't. Likely a cross-fund/channel identifier — needs admin clarification before Phase 2.
11. **Liaison/`رابط`** is free-text (`سید`, `روابط`, ...). Likely a small fixed set; should become an enum/lookup with admin input.

---

## 7. Deliverables Summary

For Phase 1:

1. `migrate.py` (or equivalent) — Excel → DB, with a JSON validation report.
2. SQL schema (and Alembic migration) implementing §3.1.
3. Web dashboard implementing the pages in §5.2.
4. README with: how to run migration, how to run the web app, environment variables, how to drop and re-run on a new Excel snapshot.

Out of scope for Phase 1: any write/edit UI, payment recording, notifications, multi-asset accounting, role-based auth, mobile app.

---

## 8. Open Questions for Admins

Before/during Phase 1 build, confirm:

1. Are loan numbers **globally unique** or unique-per-year? (Sample uses `15xx` for 1404, `25xx` for 1405 — looks year-prefixed but unsure if enforced.)
2. The unit of `مبلغ` — is `5` = 5 million toman, 5 thousand, or 5 raw toman? Need a single canonical unit.
3. What does `ش.کانال` mean operationally? Is it always set by a specific kind of loan?
4. Liaison (`رابط`) values — is there a fixed list (`سید`, `روابط`, ...)?
5. For loans in gold: how are they recorded today (if at all)?
6. Should the dashboard show 1404's sample-data redacted names (`نفر 1`, ...) verbatim, or should we plan a name-mapping step for the real production sheet?
