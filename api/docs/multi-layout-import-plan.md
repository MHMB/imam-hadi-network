# Multi-Layout Importer — As-Built Design

Status: **implemented** (branch `feat/multi-layout-importer`).
Source of truth: the production workbook (`real_data.xlsm`, sha `0b6a6293…`),
sheets `سال 1401`…`سال 1405` + `موضوعات` + `افراد` (+ `شاذ`, `موجودی صندوق` — see §5).

The workbook is authoritative: the importer adapts to the file, never the
reverse.  Everything the sheets record lands in the DB; everything odd is
surfaced as a `data_issue` row instead of being dropped.

---

## 1. Verified layout map

The ledger format changed every year.  All facts below were probed
cell-by-cell against the production workbook.

| Year | shape | data row | step | loan# | borrower | total | lender | amount | topic | guarantor | grid | grid encoding |
|------|-------|----------|------|-------|----------|-------|--------|--------|-------|-----------|------|----------------|
| 1401 | paired (2 rows / contribution) | 3 | 2 | B | F | E | K (top) | L (bottom) | — | J | P..AM = 24 mo (1401/01→1402/12) | day top / amount bottom |
| 1402 | paired | 3 | 2 | B | F | E | K (top) | L (bottom) | — | J | P..AM = 24 mo (1402/01→1403/12) | day top / amount bottom |
| 1403 | paired | 4 | 2 | B | E | F | J (top) | K (top) | — | I | M..AL = 26 mo (1403/01→1405/02) | **amounts only, no day row** |
| 1404 | paired | 4 | 2 | B | E | G | L | N (top) | H | — | P..AO = 26 mo (1404/01→1406/02) | day top / amount bottom |
| 1405 | Excel table (1 row / contribution) | 3 | 1 | B | G | H | J | K | D | F | M.. = 17 (day, amount) col pairs (1405/01→1406/05) | column pairs |

Other verified facts:

- **Paid = green fill (`#00B050` family) on the amount cell — universally.**
  The light-blue (`#00B0F0`) fills in سال 1405 sit on *day* cells only and
  carry no status information.  1401/1402's `SumifColor` balance formulas
  confirm the colour-sum semantics.
- Per-contribution grid amounts sum to the contribution amount
  (spot-verified 387/387, 384/384, 393/393, 323/325, 236/238 per year).
- `افراد` master: 350 people, **zero phone numbers**.  Names are the only
  identity that exists.
- 1401/1402 carry real Gregorian date columns (`تاریخ واریز`, `موعد بازگشت`,
  `بازگشت`, `تسویه`) — deferred to Phase 2; the Persian month grid is used
  for installments, consistent with 1403–1405.

## 2. What the engine does (`parsers/layout.py` + `parsers/engine.py`)

Each year is a `YearLayout` value (column map + `GridEncoding` + explicit
`(year, month)` grid span).  One generic `parse_year()` walks any of them:
group starts where col A (`ردیف`) holds a literal; contribution rows read
lender + amount (+ `amount_row_offset` for the bottom-row years); grids
decode per encoding.  `year_parser_for()` resolves layouts from the
registry; 1406+ rebases the 1405 table layout.  `year_1404.py` /
`year_1405.py` remain as thin compatibility wrappers.

"All data lands" fallbacks (each emits an issue):

- blank loan number → synthesised `بدون‌شماره-r<row>` (warning);
- blank/formula borrower → loan kept, no borrower party (warning);
- blank/zero total → Σ of lender amounts (warning); if still ≤ 0 the loan
  cannot satisfy the DB `total_amount > 0` CHECK → skipped with an
  **error** issue (62 never-funded request rows in 1401/1402);
- topic-less layouts (1401–1403) → default topic `نامعلوم` silently;
  blank topic cells on 1404/1405 → same default + warning;
- zero-amount grid cells skipped (info) — DB `amount > 0` CHECK;
- 1403's day-less grid dates everything to day 1 **without** spamming
  `missing_day` issues (it's the encoding's resolution, not a data gap).

## 3. Person identity (`importer/names.py`)

No phones exist, so names are identity.  `match_key()` collapses spelling
variants (NFC, Arabic `ي/ك` → Persian `ی/ک`, ZWNJ stripped, **all
whitespace removed**); `ALIASES` maps confirmed same-entity surface forms
(`صندوق امام هادی`, `صندوق` → `صندوق امام هادی(ع)`).  Placeholder phones are
`+0__<sha256(key)[:16]>` — deterministic per identity, stable across
re-imports, and inside `String(32)` for arbitrarily long names (the old
`+0__<name>__` scheme overflowed and broke the duplicate-phone check).

The writer resolves every loan reference through `resolve_key()` and
**auto-creates** persons the افراد master doesn't list (~700 of the ~1,030
distinct names) — each still flagged `unresolved_person` so admins can
extend افراد.  Other `صندوق…` lenders (امام زمان، سلمان، قرض الحسن، …) are
genuinely distinct entities and stay separate.

## 4. Writer changes (`importer/writer.py`)

- **Repeat-lender merge**: ledgers record one row per *contribution* and
  the same lender funds one loan up to **74 times** (pooled loans).  The
  schema's `unique_role_person` wants one party per (loan, role, person), so
  `_merged_parties()` sums amounts and concatenates installments — no
  repayment detail lost, no constraint violation (this exact violation
  aborted the first production import).
- **Referenced-topic upsert**: a loan whose topic isn't in موضوعات gets the
  topic created instead of the loan silently skipped.
- **Master dedup guard**: افراد itself can list one person under two
  spellings (same identity key → same placeholder phone); the second
  occurrence refreshes instead of double-inserting.
- `write_parse_result` returns `(Import, deduped)` — the sha-dedup flag is
  now a fact from the writer, not a timing heuristic in the runner.
- Year-scoped replace, single transaction, sha-dedup: unchanged.

No schema migration was needed.

## 5. Out of scope (deliberate)

- **`شاذ`** — gold-coin loans (ربع/نیم/تمام سکه, years 1385–86) with
  formula-priced amounts; doesn't fit the money model.  Phase 2 decision.
- **`موجودی صندوق`** — fund balance snapshot; derived data the DB recomputes.
- 1401/1402 Gregorian date columns → Phase 2 (`paid_persian_date` fields
  already reserved on `installment`).

## 6. Result on the production workbook

```
years=[1401..1405]  loans=1571  persons≈1,049  parties=4,650  installments=5,880
issues=2,123 (89 errors = 62 never-funded skips + total mismatches)
per-year loans: 1401=240, 1402=351, 1403=512, 1404=326, 1405=142
```

Worst pooled loan (#1637): ~310 contribution rows → 110 unique parties; the
fund's 74 rows merge to one 527.55 party with 178 dated installments.

## 7. Rollout

1. PR `feat/multi-layout-importer` → main (CI runs api tests).
2. `images` workflow publishes `ghcr.io/...-api:latest` on merge.
3. `make deploy` on the host (pull + `up -d`).
4. Prod: truncate any leftover import, run
   `docker exec imamhadi-api-1 python -m app.importer.cli /uploads/real_data.xlsm`,
   verify per-year counts match §6.
