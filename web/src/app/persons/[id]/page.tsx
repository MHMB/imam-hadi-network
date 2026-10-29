"use client";

import { use, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EditPersonDialog } from "@/components/person/EditPersonDialog";
import { AuditHistory } from "@/components/ui/AuditHistory";
import { Button } from "@/components/ui/form";
import { NoteBadge } from "@/components/ui/NoteBadge";
import { PlatformIcon } from "@/components/ui/PlatformIcon";
import { ErrorState, Loading } from "@/components/ui/States";
import { displayPhone, fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { useLoans, usePerson } from "@/lib/query/hooks";

const GUARANTOR_LABELS: Record<string, string> = {
  main: messages.guarantorRoleMain,
  secondary_2: messages.guarantorRole2,
  secondary_3: messages.guarantorRole3,
  secondary_4: messages.guarantorRole4,
};
const GUARANTOR_ORDER: Record<string, number> = {
  main: 0,
  secondary_2: 1,
  secondary_3: 2,
  secondary_4: 3,
};

export default function PersonDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const personId = Number(id);
  const { data, isLoading, isError } = usePerson(Number.isFinite(personId) ? personId : null);
  const [editing, setEditing] = useState(false);

  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState />;

  const { person, profile, guarantors, guarantees, brokered, by_year, upcoming, overdue } = data;

  const borrowedTotal = Number(person.total_borrowed);
  const debtRemaining = Number(person.outstanding_debt);
  const lentTotal = Number(person.total_lent);
  const receivableRemaining = Number(person.outstanding_receivable);
  const netCapital = Number(person.net_capital);

  const borrowedCount = by_year.reduce((acc, y) => acc + y.as_borrower_loans, 0);
  const lentCount = by_year.reduce((acc, y) => acc + y.as_lender_parties, 0);

  return (
    <section className="space-y-6">
      <Link href="/persons" className="text-sm text-slate-500 hover:text-slate-700">
        ← {messages.navPeople}
      </Link>

      {/* Identity + guarantor chain */}
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{person.full_name}</h1>
          {person.is_verified && <Badge tone="paid">{messages.verified}</Badge>}
          <Button className="ms-auto" onClick={() => setEditing(true)}>
            {messages.editProfile}
          </Button>
        </div>
        {(profile.contacts.length > 0 || profile.bank_account) && (
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-700">
            {profile.contacts.map((c) => (
              <span key={`${c.platform}-${c.handle}`} className="inline-flex items-center gap-1.5">
                <PlatformIcon platform={c.platform} />
                <span dir="ltr">{c.handle}</span>
                {c.is_default && (
                  <span className="rounded bg-slate-100 px-1.5 text-xs text-slate-600">
                    {messages.contactDefault}
                  </span>
                )}
              </span>
            ))}
            {profile.bank_account && (
              <span>
                {messages.bankAccount}:{" "}
                <span dir="ltr" className="font-medium">
                  {toPersianDigits(profile.bank_account)}
                </span>
              </span>
            )}
          </div>
        )}
        {(displayPhone(person.phone) || person.national_code) && (
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
            {displayPhone(person.phone) && (
              <span dir="ltr" className="font-medium">
                {displayPhone(person.phone)}
              </span>
            )}
            {person.national_code && (
              <span>
                {messages.nationalCode}: {toPersianDigits(person.national_code)}
              </span>
            )}
          </div>
        )}
        {guarantors.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
            <span className="text-xs text-slate-500">{messages.guarantors}:</span>
            {[...guarantors]
              .sort((a, b) => (GUARANTOR_ORDER[a.role] ?? 9) - (GUARANTOR_ORDER[b.role] ?? 9))
              .map((g) => (
                <Link
                  key={g.role}
                  href={`/persons/${g.person.id}`}
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium hover:underline",
                    g.role === "main" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700",
                  ].join(" ")}
                >
                  {GUARANTOR_LABELS[g.role] ?? g.role}: {g.person.full_name}
                </Link>
              ))}
          </div>
        )}
      </Card>

      {/* Financial status: borrowed / lent / net balance */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SideCard
          title={messages.profileBorrowed}
          total={borrowedTotal}
          backLabel={messages.profileRepaid}
          back={borrowedTotal - debtRemaining}
          remainingLabel={messages.profileDebtRemaining}
          remaining={debtRemaining}
        />
        <SideCard
          title={messages.profileLent}
          total={lentTotal}
          backLabel={messages.profileReturned}
          back={lentTotal - receivableRemaining}
          remainingLabel={messages.profileReceivableRemaining}
          remaining={receivableRemaining}
        />
        <div className="flex flex-col justify-center rounded-xl bg-slate-100 p-4">
          <p className="text-sm font-medium text-slate-600">{messages.profileBalance}</p>
          <p
            className={`mt-1 text-2xl font-bold ${netCapital >= 0 ? "text-paid" : "text-overdue"}`}
          >
            {fmtMoneyMT(netCapital)}
          </p>
          <p className="mt-1 text-xs text-slate-500">{messages.profileBalanceHint}</p>
        </div>
      </div>

      {/* Collapsible loans (default closed), tabs inside */}
      <LoansAccordion personId={personId} borrowedCount={borrowedCount} lentCount={lentCount} />

      {/* Each list is split by side: what this person owes vs what is owed to them. */}
      <InstallmentSection
        title={messages.profileOverdueDebt}
        tone="overdue"
        items={overdue.filter((i) => i.role === "borrower")}
      />
      <InstallmentSection
        title={messages.profileOverdueReceivable}
        tone="overdue"
        items={overdue.filter((i) => i.role === "lender")}
      />
      <InstallmentSection
        title={messages.profileUpcomingDebt}
        tone="unpaid"
        items={upcoming.filter((i) => i.role === "borrower")}
      />
      <InstallmentSection
        title={messages.profileUpcomingReceivable}
        tone="unpaid"
        items={upcoming.filter((i) => i.role === "lender")}
      />

      <GuaranteesSection guarantees={guarantees} title={messages.guaranteesTitle} />
      <GuaranteesSection
        guarantees={brokered}
        title={messages.brokeredTitle}
        labels={BROKERED_LABELS}
      />
      <AuditHistory entity="person" id={person.id} />
      {editing && <EditPersonDialog open onClose={() => setEditing(false)} detail={data} />}
    </section>
  );
}

function SideCard({
  title,
  total,
  backLabel,
  back,
  remainingLabel,
  remaining,
}: {
  title: string;
  total: number;
  backLabel: string;
  back: number;
  remainingLabel: string;
  remaining: number;
}) {
  const pct = total > 0 ? Math.round((Math.max(back, 0) / total) * 100) : 0;
  return (
    <Card>
      <p className="text-sm font-medium text-slate-600">{title}</p>
      <dl className="mt-2 space-y-1 text-sm">
        <div className="flex items-baseline justify-between">
          <dt className="text-slate-500">{messages.loanTotal}</dt>
          <dd className="font-semibold text-slate-900">{fmtMoneyMT(total)}</dd>
        </div>
        <div className="flex items-baseline justify-between">
          <dt className="text-slate-500">{backLabel}</dt>
          <dd className="font-medium text-paid">{fmtMoneyMT(Math.max(back, 0))}</dd>
        </div>
        <div className="flex items-baseline justify-between">
          <dt className="text-slate-500">{remainingLabel}</dt>
          <dd className={`font-medium ${remaining > 0 ? "text-overdue" : "text-slate-400"}`}>
            {fmtMoneyMT(remaining)}
          </dd>
        </div>
      </dl>
      {total > 0 && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-paid" style={{ width: `${pct}%` }} />
        </div>
      )}
    </Card>
  );
}

const LOANS_PAGE_SIZE = 500; // API max — covers every person in the current data

function LoansAccordion({
  personId,
  borrowedCount,
  lentCount,
}: {
  personId: number;
  borrowedCount: number;
  lentCount: number;
}) {
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<"borrowed" | "lent">(borrowedCount > 0 ? "borrowed" : "lent");

  // Lazy: nothing is fetched until the accordion opens; each tab fetches once.
  const borrowed = useLoans(
    { borrower_id: personId, page_size: LOANS_PAGE_SIZE },
    open && tab === "borrowed",
  );
  const lent = useLoans(
    { lender_id: personId, page_size: LOANS_PAGE_SIZE },
    open && tab === "lent",
  );
  const active = tab === "borrowed" ? borrowed : lent;

  const totalCount = borrowedCount + lentCount;
  if (totalCount === 0) return null;

  return (
    <Card className="p-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-start"
      >
        <span className="text-lg font-semibold text-slate-900">
          {messages.profileLoans}{" "}
          <span className="text-sm font-normal text-slate-500">
            ({toPersianDigits(totalCount)} {messages.itemsCount})
          </span>
        </span>
        <span aria-hidden className="text-slate-500">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100">
          <div role="tablist" className="flex gap-2 px-4 pt-3">
            <TabChip
              active={tab === "borrowed"}
              onClick={() => setTab("borrowed")}
              label={`${messages.profileLoansBorrowed} (${toPersianDigits(borrowedCount)})`}
            />
            <TabChip
              active={tab === "lent"}
              onClick={() => setTab("lent")}
              label={`${messages.profileLoansLent} (${toPersianDigits(lentCount)})`}
            />
          </div>

          <div className="mt-3">
            {active.isLoading && <Loading />}
            {active.isError && <ErrorState />}
            {active.data && active.data.items.length === 0 && (
              <p className="px-4 pb-4 text-sm text-slate-500">{messages.empty}</p>
            )}
            {active.data && active.data.items.length > 0 && (
              <>
                <ul className="divide-y divide-slate-100 border-t border-slate-100">
                  {active.data.items.map((loan) => (
                    <li key={loan.id} className="px-4 py-2.5 text-sm">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                        <Link
                          href={`/loans/${loan.id}`}
                          className="font-medium text-slate-900 hover:underline"
                        >
                          {messages.loanNumber} {toPersianDigits(loan.loan_number)}
                          <span className="font-normal text-slate-500">
                            {" "}
                            · {toPersianDigits(loan.persian_year)} · {loan.topic_name}
                          </span>
                        </Link>
                        {loan.has_note && <NoteBadge flagged={loan.note_flagged} />}
                        {loan.source_platform && (
                          <PlatformIcon platform={loan.source_platform} size={18} />
                        )}
                        <span className="flex items-baseline gap-3 text-slate-600">
                          <span>{fmtMoneyMT(Number(loan.total))}</span>
                          <span
                            className={
                              Number(loan.remaining) > 0 ? "text-overdue" : "text-slate-400"
                            }
                          >
                            {messages.remaining}: {fmtMoneyMT(Number(loan.remaining))}
                          </span>
                          <Badge tone={loan.status === "settled" ? "settled" : "active"}>
                            {loan.status === "settled" ? messages.settled : messages.active}
                          </Badge>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
                {active.data.total > active.data.items.length && (
                  <p className="px-4 py-2 text-xs text-slate-500">
                    و {toPersianDigits(active.data.total - active.data.items.length)}{" "}
                    {messages.andMore}…
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

function TabChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={[
        "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

function InstallmentSection({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "overdue" | "unpaid";
  items: NonNullable<ReturnType<typeof usePerson>["data"]>["upcoming"];
}) {
  if (items.length === 0) return null;
  return (
    <Card className="p-0">
      <h2 className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 px-4 py-3 text-lg font-semibold text-slate-900">
        <span>
          {title} ({toPersianDigits(items.length)})
        </span>
        <span className="text-sm font-medium text-slate-600">
          {fmtMoneyMT(items.reduce((acc, i) => acc + Number(i.amount), 0))}
        </span>
      </h2>
      <ul className="divide-y divide-slate-100">
        {items.map((i, idx) => (
          <li
            key={`${i.loan_id}-${idx}`}
            className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
          >
            <Link
              href={`/loans/${i.loan_id}`}
              className="font-medium text-slate-900 hover:underline"
            >
              {messages.loanNumber} {toPersianDigits(i.loan_number)}
            </Link>
            <span className="text-slate-600">{i.counterparty_name}</span>
            <span className="text-slate-600">{JALALI_MONTHS[i.due_persian_month - 1]}</span>
            <span className="text-slate-700">
              {fmtJalaliDate(i.due_persian_year, i.due_persian_month, i.due_day_of_month)}
            </span>
            <span className="font-medium">{fmtMoneyMT(Number(i.amount))}</span>
            <Badge tone={tone}>{tone === "overdue" ? messages.overdue : messages.pending}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const GUARANTEES_PREVIEW = 8;

type SectionLabels = { count: string; total: string; remaining: string; overdue: string };
const GUARANTEE_LABELS: SectionLabels = {
  count: messages.guaranteesLoans,
  total: messages.guaranteesTotal,
  remaining: messages.guaranteesRemaining,
  overdue: messages.guaranteesOverdue,
};
const BROKERED_LABELS: SectionLabels = {
  count: messages.brokeredLoans,
  total: messages.brokeredTotal,
  remaining: messages.guaranteesRemaining,
  overdue: messages.brokeredOverdue,
};

/** Loans this person guaranteed (or brokered as رابط): how much is still being repaid and how much is late. */
function GuaranteesSection({
  guarantees,
  title,
  labels = GUARANTEE_LABELS,
}: {
  guarantees: NonNullable<ReturnType<typeof usePerson>["data"]>["guarantees"];
  title: string;
  labels?: SectionLabels;
}) {
  const [all, setAll] = useState(false);
  if (guarantees.loan_count === 0) return null;
  const overdue = Number(guarantees.overdue);
  const shown = all ? guarantees.loans : guarantees.loans.slice(0, GUARANTEES_PREVIEW);
  return (
    <Card className="p-0">
      <h2 className="border-b border-slate-100 px-4 py-3 text-lg font-semibold text-slate-900">
        {title}
      </h2>
      <dl className="grid grid-cols-2 gap-4 px-4 py-3 text-sm md:grid-cols-4">
        <div>
          <dt className="text-slate-500">{labels.count}</dt>
          <dd className="mt-0.5 font-semibold text-slate-900">
            {toPersianDigits(guarantees.loan_count)}
            <span className="ms-1 text-xs font-normal text-slate-500">
              ({toPersianDigits(guarantees.active_count)} {messages.guaranteesActive})
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{labels.total}</dt>
          <dd className="mt-0.5 font-semibold text-slate-900">
            {fmtMoneyMT(Number(guarantees.total))}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{labels.remaining}</dt>
          <dd className="mt-0.5 font-semibold text-slate-900">
            {fmtMoneyMT(Number(guarantees.remaining))}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{labels.overdue}</dt>
          <dd className={`mt-0.5 font-semibold ${overdue > 0 ? "text-overdue" : "text-slate-400"}`}>
            {fmtMoneyMT(overdue)}
          </dd>
        </div>
      </dl>
      <ul className="divide-y divide-slate-100 border-t border-slate-100">
        {shown.map((ln) => (
          <li
            key={ln.loan_id}
            className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-2.5 text-sm"
          >
            <Link
              href={`/loans/${ln.loan_id}`}
              className="font-medium text-slate-900 hover:underline"
            >
              {messages.loanNumber} {toPersianDigits(ln.loan_number)}
              <span className="font-normal text-slate-500">
                {" "}
                · {toPersianDigits(ln.persian_year)} · {ln.borrower_name}
              </span>
            </Link>
            <span className="flex items-baseline gap-3 text-slate-600">
              <span>{fmtMoneyMT(Number(ln.total))}</span>
              {Number(ln.overdue) > 0 ? (
                <Badge tone="overdue">
                  {messages.overdue}: {fmtMoneyMT(Number(ln.overdue))}
                </Badge>
              ) : Number(ln.remaining) > 0 ? (
                <span>
                  {messages.remaining}: {fmtMoneyMT(Number(ln.remaining))}
                </span>
              ) : (
                <Badge tone="settled">{messages.settled}</Badge>
              )}
            </span>
          </li>
        ))}
      </ul>
      {guarantees.loans.length > GUARANTEES_PREVIEW && (
        <button
          type="button"
          onClick={() => setAll((v) => !v)}
          className="w-full border-t border-slate-100 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {all
            ? messages.showLess
            : `${messages.showAll} (${toPersianDigits(guarantees.loans.length)})`}
        </button>
      )}
    </Card>
  );
}
