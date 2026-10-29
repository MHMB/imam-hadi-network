# Write mode — system design

**Status:** Proposed · **Date:** 1405/08/07 (2026-10-29) · **Deciders:** network admin (product), dev
**Input:** 15 requirements R1–R15 in [`voices-fixes/TASKS.md`](../../voices-fixes/TASKS.md).
**Designs:** home page — claude.ai/artifact/YbURReD5oduRCdLgCyFKVK · loan flow — claude.ai/artifact/W3N4np8ohKtoJyjs7i1E13

---

## 1. Context

Today the app is a **read-only mirror of one Excel workbook**. The importer does, per year in the file,
`DELETE loan WHERE persian_year IN (…)` (cascades to parties + installments) and re-inserts everything;
persons are upserted by phone, guarantor slots are wiped and rebuilt. An installment is binary
(`paid`/`unpaid`, read from cell colour) with no paid date. There is no user identity in the API —
Traefik basic-auth with one shared password guards everything.

The voice notes ask for the opposite: staff **create loans, record payments, edit people**. That breaks
three assumptions at once:

| Assumption today | Why it breaks |
|---|---|
| Excel is the source of truth | Re-import deletes every app-entered loan/payment in the imported years |
| Installment is paid or not | R13: partial payments, over-payment carried forward, payments spread over months |
| Nobody needs to know who did what | Several staff will write money records; mistakes must be traceable and reversible |

Constraints: single VPS, one Postgres, ~1.2k persons / ~2k loans / ~7k installments (tiny); 1–5 staff;
Persian RTL UI; amounts in **million toman, 3 decimals** (= 1,000 toman resolution); dates are Jalali
(y, m, d) triples. Stack stays: FastAPI + SQLAlchemy async + Alembic + Next.js + react-query.

---

## 2. Decisions (ADRs)

### ADR-1 — Source of truth: one-time cutover from Excel to the app

| Option | Complexity | Data safety | Notes |
|---|---|---|---|
| **A. Cutover** (recommended): final import, then the app is the truth; importer refuses to touch years that hold app data | Low | High | Excel stays available read-only as archive / for new historical years |
| B. Coexist: `origin` flag, importer deletes only `origin='import'` rows | Medium | **Low** | Payments recorded in the app on *imported* installments are still destroyed, because installment rows are rebuilt from cell colour |
| C. Keep Excel as truth, app stays read-only | — | — | Rejects R5, R11–R13 |

**Decision: A.** Add `loan.origin ('import'|'app')`, make `loan.import_id` nullable, and give the importer a
**guard**: before deleting a year it checks for any `origin='app'` loan or any payment in that year and
fails the import with a clear Persian error (`سال ۱۴۰۵ داده ثبت‌شده در سامانه دارد…`). A
`--force` CLI flag exists for the admin, never in the HTTP upload. The admin chooses the cutover day
(Q1); after it, the Excel is no longer edited.

**Consequences.** Easier: every page has one truth; payments are safe. Harder: corrections that used to
be "fix the cell and re-upload" become in-app edits (so R12/R13 must include edit + undo). Revisit if the
team insists on keeping Excel as a parallel ledger (would need two-way sync — not recommended).

### ADR-2 — Payments: a payment ledger with allocations

| Option | Partial / carry-forward | Undo | Audit |
|---|---|---|---|
| A. Flip `installment.status` + paid date | ✗ | weak | ✗ |
| B. `installment.amount_paid` only | ✓ | no history | ✗ |
| **C. `payment` + `payment_allocation` rows; `installment.amount_paid` kept in sync** (recommended) | ✓ | void the payment | ✓ |

**Decision: C.**
- `payment` = money that actually arrived: loan, payer (borrower), amount, paid date (Jalali, typed by
  hand), note, actor, `voided_at`.
- `payment_allocation` = how that money was spread: (payment, installment, amount).
- `installment.amount_paid` (denormalised Σ live allocations) and `status ∈ {unpaid, partial, paid}`
  are updated **in the same transaction** as the allocations, so every read query stays a cheap
  column read.
- **Allocation rule (R13):** oldest due first, across the loan's lenders, ties broken by lender
  display order (Q2 may change "across lenders" to "same lender first"). The UI shows the split
  before saving and the admin can override it (R13 "edit the ledger first").
- **Quick settle** (R5 «تسویه سریع قسط», R13 "tick installments") = one payment whose allocation is
  exactly the ticked installments' remaining amounts.
- **Undo** = void the payment (soft): allocations stop counting, `amount_paid`/`status` recomputed.
  Nothing financial is ever hard-deleted.
- **Imported history:** green cells become `amount_paid = amount, status = paid` with no payment row
  (legacy). Remaining is always `amount − amount_paid`.

**One remaining expression.** Today ~15 queries in kpi / loan / person / topic / analytics / overdue sum
`amount WHERE status='unpaid'`. They all switch to a single helper
`remaining_expr = Installment.amount - Installment.amount_paid` (services/money.py). This refactor
lands **before** payments exist, with tests proving identical numbers.

### ADR-3 — Loan creation and the installment ledger

- **Number:** next = `max(numeric loan_number) + 1` across all years (current max 2258; numbers are one
  sequence), taken with `SELECT … FOR UPDATE` on a one-row counter to avoid two staff getting the same
  number. Year = current Jalali year unless the admin changes it.
- **Form (R12):** borrower, topic, guarantor (per loan), liaison, source platform (R11), lenders with
  amounts (Σ = total, validated), first due month, number of months, note + "important" flag (R14).
- **Schedule modes:**
  - **A «همه متناسب»** — each month's payment = total/n, split across lenders by their share. Rounded to
    3 decimals; the rounding remainder goes to the last month of each lender so every lender's row sums
    exactly to their amount.
  - **B «اولویت‌دار»** — the generated grid (lender × month) opens editable; any cell can change. Save is
    allowed only when every lender row sums to that lender's amount.
- **One generator, server-side:** `POST /api/loans/schedule-preview` returns the grid; the form edits it;
  `POST /api/loans` saves loan + parties + installments atomically and re-validates. The frontend never
  computes money.
- **Editing later:** `PUT /api/loans/{id}/schedule` may change only unpaid remainders; cells with
  allocations are locked to `≥ amount_paid`.

### ADR-4 — Identity, roles and audit

| Option | Effort | Gives |
|---|---|---|
| **A. Per-user basic-auth at Traefik; API reads the username from the `Authorization` header** (recommended now) | Low | Who did what; no login UI |
| B. App login (sessions/JWT, user table, password reset) | High | Roles in-app, logout |

**Decision: A now, B later.** Each staff member gets their own htpasswd line; Traefik already
validates the password, the API only decodes the username (the API is not reachable except through
Traefik — it has no published port). A `user` row is upserted on first sight (username, display name,
role). Roles: `admin` (everything, incl. imports, void payments, edit schedules) and `support`
(create loans, record payments, edit contacts). Every write appends to `audit_log` (actor, action,
entity, id, before/after JSON, time). CORS gains PUT/PATCH/DELETE.

### ADR-5 — People: contacts, bank account, guarantor and liaison links

- **Phone (R11):** required when a profile is saved from the app; validated as Iranian mobile and
  unique. 1,206 persons currently carry placeholder phones (`+0__…`); saving a real number replaces the
  placeholder (safe after cutover — the importer matches by phone).
- **Contacts:** new `person_contact (person, platform, handle, is_default)`; platforms enum
  `telegram | bale | eitaa | whatsapp | rubika | phone_call | in_person`; one default per person
  (partial unique index). The old free-text `messenger` migrates into it.
- **Bank account:** `person.bank_iban` (IR + 24 digits, validated) and `person.bank_card` (16 digits,
  Luhn-checked) — both optional (Q4).
- **Loan source (R11):** `loan.source_platform` (same enum, nullable for history); icons are small
  inline SVG marks per platform.
- **Guarantor — two different things, both kept:**
  - *member guarantor* — who vouches for the person (`person_guarantor`, slot `main`, from the افراد
    sheet). This is the «ضامن» column and filter on the persons list (R8).
  - *loan guarantor* — `loan.guarantor_id` (1,045 of 2,049 loans have one). This drives the guarantee
    record on the profile (R9) and the guarantor chip on the loan page (R15).
- **Liaison (R9):** `liaison_label` holds mostly person names (ساجد / سیدساجد موسوی / علی ربیعی… with
  spelling variants) plus channel labels («روابط», «روابط عمومی»: 626 loans). Add
  `loan.liaison_person_id`, backfilled by the importer's name matcher; unmatched values stay as label
  only. The profile then shows loans brokered, active vs settled.

### ADR-6 — Frontend building blocks (no new dependencies)

Forms use native inputs + **zod** (already installed) for validation; Jalali dates are three inputs
(day / month select / year) with jalaali-js validation instead of a picker library — the range
filter (R6) uses the same control twice. A small `<Dialog>` on native `<dialog>`; a
`<PersonCombobox>` (search-as-you-type on `/api/persons?q=`); a shared `<SortableTh>` + URL-state
filter hook extracted from the loans page; a JSON `post/patch` helper in `lib/api/client.ts` that
surfaces 422 detail per field; inline success/error (`role=status|alert`) like the uploader. Mutations
invalidate `loans, persons, kpi, overdue, topics, analytics`.

---

## 3. Data model changes (one migration per phase)

```text
user               id, username UNIQUE, display_name, role(admin|support), created_at
audit_log          id, user_id→user, action, entity, entity_id, before JSONB, after JSONB, at
loan               + origin(import|app) default 'import'
                   ~ import_id NULL-able
                   + source_platform NULL, + liaison_person_id→person NULL
                   + note TEXT NULL, + note_flagged BOOL default false, + created_by→user NULL
installment        + amount_paid NUMERIC(18,3) default 0  (CHECK 0 ≤ amount_paid ≤ amount)
                   ~ status: unpaid | partial | paid  (CHECK consistent with amount_paid)
payment            id, loan_id→loan, payer_id→person, amount>0, paid_y/m/d, note,
                   created_by→user, created_at, voided_at NULL, voided_by→user NULL
payment_allocation payment_id→payment, installment_id→installment, amount>0, PK(payment, installment)
person             + bank_iban, + bank_card  (messenger → person_contact)
person_contact     id, person_id→person, platform, handle, is_default
                   UNIQUE(person_id) WHERE is_default
loan_number_seq    one-row counter (or a Postgres SEQUENCE seeded at 2258)
```

Backfill: `amount_paid = amount WHERE status='paid'`; `origin='import'` for all existing loans;
`liaison_person_id` from name matching.

---

## 4. API (new or changed)

| Method | Path | Purpose | R |
|---|---|---|---|
| GET | `/api/kpi` | + `overdue_loans`, `overdue_amount` | R3 |
| GET | `/api/loans` | default sort `loan_number desc`; + `has_note` filter; items + `source_platform`, `note_flagged` | R1, R11, R14 |
| GET | `/api/installments/overdue` | + `year`, `due_from`, `due_to` | R6 |
| GET | `/api/persons` | + `guarantor_id`, `sort` (lent, borrowed, net, overdue), items + `guarantor`, `overdue_total` | R8 |
| GET | `/api/persons/{id}` | overdue split `debt`/`receivable`; + `guarantees`, `brokered`, `monthly` | R7, R9, R10 |
| GET | `/api/persons/guarantors` | distinct member guarantors for the filter dropdown | R8 |
| PATCH | `/api/persons/{id}` | name, phone (required), bank, contacts | R11 |
| POST | `/api/loans/schedule-preview` | generate grid from form input | R12 |
| POST | `/api/loans` | create loan + parties + installments | R12 |
| PATCH | `/api/loans/{id}` | topic, guarantor, liaison, platform, note/flag | R11, R14 |
| PUT | `/api/loans/{id}/schedule` | edit unpaid part of the ledger | R12, R13 |
| POST | `/api/loans/{id}/payments/preview` | proposed allocation for an amount | R13 |
| POST | `/api/loans/{id}/payments` | record payment (amount or ticked installments) | R5, R13 |
| POST | `/api/payments/{id}/void` | undo (admin) | R13 |
| GET | `/api/me` | current user + role (drives which buttons show) | ADR-4 |

All writes: one transaction, explicit commit, audit row, 422 with per-field Persian messages.

---

## 5. Build order

Each phase is one PR, deployable on its own; numbers already correct before any write exists.

| Phase | Scope | R | Schema | Why here |
|---|---|---|---|---|
| **P0 — Quick fixes** | Loans default sort; topic share by amount; person overdue split; overdue year + date-range filters; home KPIs (active loans, overdue loans, overdue amount); overdue → own nav item, charts up | R1 R2 R3 R4 R6 R7 | none | Pure read changes, visible today, zero risk |
| **P1 — Persons insight** | Persons list: «ضامن» column + guarantor filter, overdue column, server-side sort; profile: guarantee record, monthly paid/received; liaison person backfill + brokered record | R8 R9 R10 | `liaison_person_id` | Read-only; finishes the "understand" side before "write" |
| **P2 — Write foundation** | `remaining_expr` refactor (no number changes, proven by tests); `amount_paid`/partial status; `origin`, nullable `import_id`, importer guard; user + audit; per-user basic-auth; CORS; JSON client + form kit (Dialog, zod, Jalali date, PersonCombobox, URL filters) | ADR-1/2/4/6 | user, audit_log, loan.origin, installment.amount_paid | Everything after needs it; ships invisible |
| **P3 — People editing** | Profile edit: phone required, bank, contacts with default; loan `source_platform` + icons | R11 | person_contact, bank, source_platform | Smallest write; proves auth + audit end-to-end |
| **P4 — Create loans** | New-loan form, schedule modes A/B, preview, save; «ساخت سریع قرض» on home; loan note + flag badge | R12 R5(a) R14 | loan note, number seq | Depends on P2 + P3 (platform) |
| **P5 — Payments** | Record payment (amount → FIFO preview / tick installments), partial + carry-forward, void, schedule edit; «تسویه سریع قسط» on home | R13 R5(b) | payment, payment_allocation | Highest-risk money logic, on a proven base |
| **P6 — Loan page v2** | Loan-flow visualization with guarantor + liaison chips, payment actions inline | R15 | none | Uses everything above |
| **Cutover** | Final Excel import, admin freezes the workbook | ADR-1 | — | Between P2 and P4 (before the first app-created loan) |

Out of scope (noted for later): «امتیاز خوش‌حسابی» score column (R8 leaves space for it); app login
(ADR-4 B); notifications/SMS for reminders.

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Re-import wipes app data | ADR-1 guard; HTTP upload can never force |
| Money rounding drift | Server-only generation; per-lender row sums enforced by tests and a DB check in the service |
| Two staff paying the same installment | Row lock (`SELECT … FOR UPDATE`) on the loan's installments during allocation |
| Refactor changes historical numbers | P2 snapshot tests compare every KPI / loan / person / topic total before vs after on the real workbook |
| Placeholder phones vs required phone | Only enforced when saving the edit form; list pages unaffected |

---

## 7. Decisions (answered 1405/08/07)

| Q | Decision | Source |
|---|---|---|
| Q1 Cutover | Excel stays the source **during the test period** (another update arrives today). At **end of testing** the workbook is retired and the app is the only source. The xlsm import feature stays in the system. | user |
| Q2 Over-payment | Default allocation follows the **installment ledger order** (oldest due first, as the schedule says); the admin can **edit the split** and choose who gets what. A payment larger than the whole remaining balance → **warning**, and only after the admin confirms is the excess stored as the **borrower's credit** on the loan. | user |
| Q3 Roles | One role for now: **admin**, with full edit rights. **Every admin edit is logged with before / after state** (who, when, what changed). | user |
| Q4 Bank | One optional **account-number** field. Phone is the only required profile field. | voice 09.52.14 |
| Q5 «سرمایه نزد صندوق» | = `net_capital` (receivable − debt), as the app already labels it. | existing app |
| Q6 «ماهانه» (A2.6) | Per month: amount **lent** and amount **borrowed** (new loans), not installment payments. Open: loan date proxy + placement. | user |
| Q7 Sidebar «داینامیک» | The global sidebar becomes **collapsible**: collapsed = hidden, with a menu (hamburger) icon; click opens it, click again hides it. | user |
| Q8 Liaison | Link رابط to a person (implied by "how much they brokered / settled"); «روابط» / «روابط عمومی» stay a channel label. | voices 08.43.52, 08.44.00 |
| Q9 Platforms | Telegram, Bale, Eitaa (named in voice), one default per person. | voice 09.52.14 |

**Consequences for ADR-1 (cutover) during the test period.** Re-importing a year deletes app-created
data in that year. While testing, the importer **warns** and requires an explicit admin confirmation
(«داده‌های ثبت‌شده در سامانه برای سال ۱۴۰۵ پاک می‌شود») instead of refusing; at end of testing it
switches to **refuse** (a config flag, `IMPORT_GUARD=confirm|refuse`).

**Consequences for ADR-2 (payments).** Credit = the part of a confirmed payment not allocated to any
installment (`payment.amount − Σ allocations`); shown on the loan and the borrower's profile. No extra table.

**Consequences for ADR-4 (auth).** No role column is needed yet; every user is admin. `audit_log`
stores `before` and `after` JSON for every write, and the loan / person pages get a «تاریخچه تغییرات» view.
