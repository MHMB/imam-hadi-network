# Voice-note requirements — 1405/08/07 (2026-10-29)

20 voice notes, transcribed with mlx-whisper (large-v3-turbo, Persian). Obvious mis-hearings fixed
(«زامن» → ضامن, «محوقات» → معوقات, «سی سد» → سیصد, «ساخت سری» → ساخت سریع).
**Duplicates skipped:** 09.52.35 = 09.52.27; 09.52.51 and 09.52.56 = 09.52.45. → **17 unique notes**,
merged below into **15 requirements** (R-ids are referenced by `docs/write-mode/DESIGN.md`).

| R | Note(s) | Page | Requirement | Kind |
|---|---|---|---|---|
| R1 | 09.51.18 | Loans | Default sort: loan number, newest first | change |
| R2 | 08.43.44 | Topics | Share % by **amount**, not loan count | change |
| R3 | 09.52.20 | Home | KPI cards: drop «تعداد افراد», add «قرض‌های فعال»; replace «اقساط معوق» with «قرض‌های معوق» (a loan with ≥1 late installment) plus the total overdue amount beside it | change |
| R4 | 09.52.27 (+09.52.35) | Home, nav | Overdue table leaves the home page → own sidebar item; charts move up | change |
| R5 | 09.52.45 (+2 dupes) | Home | Two buttons: «ساخت سریع قرض» and «تسویه سریع قسط» | feature (needs R12, R13) |
| R6 | 08.43.04 | Overdue | Year filter that works + due-date range with a Jalali calendar | bug + feature |
| R7 | 08.38.20 | Person | Overdue split: «بدهی معوق» (as borrower) vs «طلب معوق» (as lender) | bug |
| R8 | 09.51.31, 09.52.07 | Persons list | Column «ضامن» (the member's guarantor) in place of «تأییدشده»; guarantor filter (searchable dropdown, filters whole table); column «جمع معوقات»; sortable: lent, borrowed, capital at fund, overdue; space for a future «امتیاز خوش‌حسابی» column | feature |
| R9 | 08.43.52 | Persons list + profile | Guarantee record: loans guaranteed, amount, amount still in installments, overdue on them; liaison record: loans brokered, settled vs active | feature |
| R10 | 08.43.15 | Person | Monthly paid vs received (with net) | feature |
| R11 | 09.52.14 | Person, Loan | Editable profile: phone **required**, bank account, messenger contacts (Telegram, Bale, Eitaa…) with one default. Each loan records the platform it came from; platform logo on loan page and in person's loan lists | feature |
| R12 | 09.53.01 (part 1) | New loan | Form: borrower, lenders → on save the installment ledger is generated. Mode A «همه متناسب» (every month split pro-rata); mode B «اولویت‌دار» (per-installment, per-lender custom split) | feature |
| R13 | 08.43.38, 09.53.01 (part 2) | Payments | Settle as scheduled (tick installments) **or** edit the ledger first, then tick. Partial and over-payments: 1.3M on a 1M installment settles it, 0.3M goes to the next; one installment can be paid over several months; paid date entered by hand | feature |
| R14 | 09.52.40 | Loan lists, profile | Loans with an important note get a badge so the admin notices; the note lives on the loan | feature |
| R15 | 08.44.00 | Loan page | Guarantor and borrower obvious in the new flow view; liaisons off the flow but one click away | design |
| — | 09.52.01 | Sidebar | «سایدبار داینامیک بشه» — unclear, see open question Q7 | ? |

General rule stated in 09.51.31: **all money is in million toman**; decimals allowed.
