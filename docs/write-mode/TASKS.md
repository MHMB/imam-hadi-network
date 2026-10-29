# Task list — voice-note requirements

Source: [`voices-fixes/TASKS.md`](../../voices-fixes/TASKS.md) (R1–R15) · design: [`DESIGN.md`](DESIGN.md).
Mark done with `[x]`. IDs are stable — reference them in commits/PRs (e.g. `feat(web): A1.3 …`).

**Phase A — no database / schema change.** Ships first.
- **A1** frontend only (uses data the API already returns).
- **A2** frontend + read-only API change (new query params / fields computed from existing tables;
  no migration, no new table, no write endpoint).

**Phase B — needs schema change / writes.** Starts after Phase A is merged and the open questions
in DESIGN.md §7 are answered.

---

## Phase A1 — frontend only

- [x] **A1.1 (R1)** Loans list: default sort = loan number, descending (send `sort=loan_number&sort_dir=desc` when no sort chosen; header shows the active arrow).
- [x] **A1.2 (R2)** Topics: «سهم» = topic total ÷ Σ totals in the year scope (amount share). Update label + tooltip; keep loan count in the row.
- [x] **A1.3 (R4)** Overdue becomes its own sidebar / bottom-nav item («اقساط معوق» → `/admin/overdue`); remove `OverduePreview` from home; charts move up.
- [x] **A1.4 (R7)** Person profile: split overdue into «بدهی معوق» (role = borrower) and «طلب معوق» (role = lender), each with its own total. Same split for upcoming.
- [x] **A1.5 (R15)** Loan page: guarantor and borrower as clear role chips in the header; liaison chip beside them (from existing `guarantor` / `liaison_label`).
- [x] **A1.6 (R15)** Loan page: loan-flow visualization (lenders → borrower → installments by due date, paid / overdue / upcoming, today line, lender filter) from existing loan detail data. Read-only: no payment buttons yet.
- [x] **A1.7** Shared pieces used by A2: extract `SortableTh` from the loans page into `components/ui`; a `useUrlFilters` hook so list filters/sort live in the URL (loans, persons, overdue).

## Phase A2 — frontend + read-only API (no migration)

- [x] **A2.1 (R3)** API `/api/kpi`: add `overdue_loans` (loans with ≥1 unpaid installment past due) and `overdue_amount` (Σ those installments). Home cards: «قرض‌های فعال» (replaces «تعداد افراد»), «قرض‌های معوق» + overdue amount (replaces «اقساط معوق»), «مجموع مانده» stays.
- [x] **A2.2 (R6)** API `/api/installments/overdue`: add `year` (loan year), `due_from` / `due_to` (Jalali `YYYY-MM-DD`). Web: year select that filters; Jalali date-range control (day / month / year inputs ×2, validated with jalaali-js); filters in URL.
- [x] **A2.3 (R8)** API `/api/persons`: return each person's member guarantor (`person_guarantor` slot `main`) and `overdue_total`; add `guarantor_id` filter and `sort` = `lent | borrowed | net | overdue` (+ `sort_dir`). New `GET /api/persons/guarantors` (distinct guarantors, for the dropdown).
- [x] **A2.4 (R8)** Persons list UI: «ضامن» column replaces «تأییدشده» (verified moves to a small badge by the name); «جمع معوقات» column; sortable headers; searchable guarantor filter that filters the whole table.
- [x] **A2.5 (R9a)** API `/api/persons/{id}`: `guarantees` block from `loan.guarantor_id` — loans guaranteed (count, list), total guaranteed, still in installments, overdue on them. Profile section «ضمانت‌ها».
- [ ] **A2.6 (R10) — on hold** until the client sends loan-number → month data. Person: per month, how much the person **lent** and how much they **borrowed** (new loans; installment payments out of scope). *Blocked: the workbook has no loan date — proxy for history = month of the loan's first installment (marked «تقریبی»); app-created loans (B4) use their real date. Confirm placement (list columns for a chosen month and/or profile monthly table).*
- [x] **A2.7 (R14a)** Loans API list item + person loan lists: expose `has_note` (existing `loan.description` not empty). Badge icon on loan rows (loans list, person accordion, overdue page); note text shown on the loan page.

- [ ] **A3.1 (Q7)** Global sidebar collapsible: a menu (hamburger) icon opens it; clicking again hides it; content takes the full width; state remembered in the browser.

---

## Phase B — schema change / writes

### B0 — Decisions (before any B work)
- [x] **B0.1** Answers to DESIGN.md §7 (Q1–Q5, Q7–Q9). Q6 «ماهانه» still open (only blocks A2.6).

### B1 — Write foundation (invisible)
- [ ] **B1.1** `services/money.py` `remaining_expr`; switch every status-sum in kpi / loan / person / topic / analytics / overdue to it; snapshot tests prove identical numbers on the real workbook.
- [ ] **B1.2** Migration: `installment.amount_paid` + status `partial`; backfill paid rows.
- [ ] **B1.3** Migration: `loan.origin`, `import_id` nullable; importer guard for years with app loans/payments — `IMPORT_GUARD=confirm` during testing (admin must tick a confirmation in the upload form), `refuse` after cutover.
- [ ] **B1.4** Migration: `user`, `audit_log` (before / after JSON on every write); API reads username from Traefik basic-auth; `GET /api/me`; CORS + PUT/PATCH/DELETE. Single role (admin) for now.
- [ ] **B1.7** «تاریخچه تغییرات» view on loan and person pages (reads `audit_log`).
- [ ] **B1.5** Web form kit: JSON `post/patch` client with 422 field errors, `<Dialog>`, zod forms, `<JalaliDateInput>`, `<PersonCombobox>`, mutation invalidation helper.
- [ ] **B1.6** Cutover at **end of testing**: final Excel import on prod, `IMPORT_GUARD=refuse` (import feature stays).

### B2 — People editing (R11)
- [ ] **B2.1** Migration: `person_contact`, `person.bank_iban`, `person.bank_card`; migrate `messenger` text.
- [ ] **B2.2** `PATCH /api/persons/{id}`: phone required + Iranian mobile + unique, bank validation, contacts with one default; audit.
- [ ] **B2.3** Profile edit dialog; contacts list with platform icons and default star.
- [ ] **B2.4** Migration `loan.source_platform`; icons on loan page and person loan lists.

### B3 — Liaison as a person (R9b)
- [ ] **B3.1** Migration `loan.liaison_person_id`; backfill by name matching (keep «روابط» / «روابط عمومی» as label).
- [ ] **B3.2** Profile section «واسطه‌گری»: loans brokered, active vs settled.

### B4 — Create loans (R12, R5a, R14b)
- [ ] **B4.1** Loan number sequence (seeded from current max 2258).
- [ ] **B4.2** `POST /api/loans/schedule-preview` — mode A pro-rata with exact per-lender rounding; mode B returns editable grid.
- [ ] **B4.3** `POST /api/loans` — atomic create, re-validation, audit; `PATCH /api/loans/{id}` (topic, guarantor, liaison, platform, note + flag).
- [ ] **B4.4** New-loan page/dialog with schedule grid; «ساخت سریع قرض» button on home.
- [ ] **B4.5** Migration `loan.note`, `loan.note_flagged`; flagged badge replaces A2.7's description badge.

### B5 — Payments (R13, R5b)
- [ ] **B5.1** Migration `payment`, `payment_allocation`.
- [ ] **B5.2** Allocation service: default = ledger order (oldest due first), admin can override the split; payment above total remaining → warning + admin confirmation → excess kept as borrower credit; row locks; void + recompute; property tests.
- [ ] **B5.3** `POST /api/loans/{id}/payments/preview`, `POST /api/loans/{id}/payments`, `POST /api/payments/{id}/void`; `PUT /api/loans/{id}/schedule` (unpaid part only).
- [ ] **B5.4** Payment dialog (amount → preview split, or tick installments), schedule edit mode; «تسویه سریع قسط» on home.
- [ ] **B5.5** Loan-flow view (A1.6) gains inline payment actions.

### Later / not scheduled
- [ ] «امتیاز خوش‌حسابی» column (R8 leaves space).
- [ ] «سایدبار داینامیک» — after Q7.
- [ ] App login (DESIGN ADR-4 option B).
