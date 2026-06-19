"use client";

import { use } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { isPastDue, todayJalali, type JalaliTriple } from "@/lib/jalali";
import { useLoan } from "@/lib/query/hooks";

type LoanData = NonNullable<ReturnType<typeof useLoan>["data"]>;

type ScheduleRow = {
  key: string;
  lenderId: number;
  lenderName: string;
  year: number;
  month: number;
  day: number;
  amount: number;
};

const byDate = (a: ScheduleRow, b: ScheduleRow) =>
  a.year - b.year || a.month - b.month || a.day - b.day;

/** Flatten every lender's installments into one list tagged with the lender,
 * then bucket by status so the admin reads a date-ordered schedule instead of
 * a per-lender grouping. */
function buildSchedule(lenders: LoanData["lenders"], today: JalaliTriple) {
  const overdue: ScheduleRow[] = [];
  const upcoming: ScheduleRow[] = [];
  const paid: ScheduleRow[] = [];
  lenders.forEach((ln) => {
    ln.installments.forEach((inst, i) => {
      const row: ScheduleRow = {
        key: `${ln.party_id}-${i}`,
        lenderId: ln.person.id,
        lenderName: ln.person.full_name,
        year: inst.due_persian_year,
        month: inst.due_persian_month,
        day: inst.due_day_of_month,
        amount: Number(inst.amount),
      };
      if (inst.status === "paid") {
        paid.push(row);
      } else if (isPastDue(row.year, row.month, row.day, today)) {
        overdue.push(row);
      } else {
        upcoming.push(row);
      }
    });
  });
  overdue.sort(byDate);
  upcoming.sort(byDate);
  paid.sort(byDate);
  return { overdue, upcoming, paid };
}

export default function LoanDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const loanId = Number(id);
  const { data, isLoading, isError } = useLoan(Number.isFinite(loanId) ? loanId : null);
  const today = todayJalali();

  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState />;

  const { loan, topic, guarantor, borrowers, lenders, totals } = data;
  const schedule = buildSchedule(lenders, today);

  const loanNumber = (loan as Record<string, unknown>).loan_number as string;
  const persianYear = (loan as Record<string, unknown>).persian_year as number;
  const channelNumber = (loan as Record<string, unknown>).channel_number as string | null;
  const liaisonLabel = (loan as Record<string, unknown>).liaison_label as string | null;
  const description = (loan as Record<string, unknown>).description as string | null;

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <Link href="/loans" className="text-sm text-slate-500 hover:text-slate-700">
          ← {messages.navLoans}
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">
          {messages.loanNumber} {toPersianDigits(loanNumber)}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <Badge tone={totals.settled ? "settled" : "active"}>
            {totals.settled ? messages.settled : messages.active}
          </Badge>
          <span>
            {messages.year}: {toPersianDigits(persianYear)}
          </span>
          <span>·</span>
          <span>{topic.name}</span>
          {liaisonLabel && (
            <>
              <span>·</span>
              <span>
                {messages.liaison}: {liaisonLabel}
              </span>
            </>
          )}
          {channelNumber && (
            <>
              <span>·</span>
              <span>
                {messages.channelNumber}: {toPersianDigits(channelNumber)}
              </span>
            </>
          )}
        </div>
        {description && <p className="text-sm text-slate-700">{description}</p>}
      </header>

      {/* Totals strip */}
      <div className="grid grid-cols-3 gap-4">
        <SummaryStat label={messages.loanTotal} value={fmtMoneyMT(Number(totals.total))} />
        <SummaryStat label={messages.paid} value={fmtMoneyMT(Number(totals.paid))} />
        <SummaryStat label={messages.remaining} value={fmtMoneyMT(Number(totals.remaining))} />
      </div>

      {guarantor && (
        <Card>
          <h2 className="text-sm font-medium text-slate-600">{messages.guarantorLoan}</h2>
          <Link
            href={`/persons/${guarantor.id}`}
            className="mt-1 inline-block font-medium text-slate-900 hover:underline"
          >
            {guarantor.full_name}
          </Link>
        </Card>
      )}

      <PartySection title={messages.borrowers} items={borrowers} />

      {/* Compact lender roster — totals only; the schedule below is by date */}
      {lenders.length > 0 && (
        <Card className="p-0">
          <h2 className="border-b border-slate-100 px-4 py-3 text-lg font-semibold text-slate-900">
            {messages.loanLenders} ({toPersianDigits(lenders.length)})
          </h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {lenders.map((ln) => (
              <li
                key={ln.party_id}
                className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-2.5"
              >
                <Link
                  href={`/persons/${ln.person.id}`}
                  className="font-medium text-slate-900 hover:underline"
                >
                  {ln.person.full_name}
                </Link>
                <span className="flex flex-wrap gap-x-4 text-xs text-slate-600">
                  <span>
                    {messages.amountLent}: {fmtMoneyMT(Number(ln.amount))}
                  </span>
                  <span className="text-paid">
                    {messages.paid}: {fmtMoneyMT(Number(ln.paid))}
                  </span>
                  <span className={Number(ln.remaining) > 0 ? "text-overdue" : "text-slate-400"}>
                    {messages.remaining}: {fmtMoneyMT(Number(ln.remaining))}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Repayment schedule, by status, each date-ordered */}
      <ScheduleTable title={messages.overdue} tone="overdue" rows={schedule.overdue} />
      <ScheduleTable title={messages.pending} tone="unpaid" rows={schedule.upcoming} />
      <ScheduleTable title={messages.paid} tone="paid" rows={schedule.paid} />
    </section>
  );
}

const TITLE_TONE: Record<string, string> = {
  overdue: "text-overdue",
  unpaid: "text-slate-900",
  paid: "text-paid",
};

function ScheduleTable({
  title,
  tone,
  rows,
}: {
  title: string;
  tone: "overdue" | "unpaid" | "paid";
  rows: ScheduleRow[];
}) {
  if (rows.length === 0) return null;
  const sum = rows.reduce((acc, r) => acc + r.amount, 0);
  return (
    <Card className="p-0">
      <div className="flex items-baseline justify-between border-b border-slate-100 px-4 py-3">
        <h2 className={`text-base font-semibold ${TITLE_TONE[tone]}`}>
          {title}{" "}
          <span className="text-sm font-normal text-slate-500">
            ({toPersianDigits(rows.length)})
          </span>
        </h2>
        <span className="text-sm text-slate-600">{fmtMoneyMT(sum)}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-2 text-start font-medium">{messages.dueDate}</th>
              <th className="px-4 py-2 text-start font-medium">{messages.repaidTo}</th>
              <th className="px-4 py-2 text-start font-medium">{messages.amount}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={r.key} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-700">
                  {fmtJalaliDate(r.year, r.month, r.day)}
                  <span className="ms-2 text-xs text-slate-400">{JALALI_MONTHS[r.month - 1]}</span>
                </td>
                <td className="px-4 py-2.5">
                  <Link href={`/persons/${r.lenderId}`} className="text-slate-900 hover:underline">
                    {r.lenderName}
                  </Link>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-900">
                  {fmtMoneyMT(r.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-base font-bold text-slate-900">{value}</p>
    </div>
  );
}

function PartySection({ title, items }: { title: string; items: LoanData["borrowers"] }) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold text-slate-900">
        {title} ({toPersianDigits(items.length)})
      </h2>
      <ul className="space-y-2">
        {items.map((p) => (
          <li key={p.party_id} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
            <div className="flex items-center justify-between">
              <Link
                href={`/persons/${p.person.id}`}
                className="font-medium text-slate-900 hover:underline"
              >
                {p.person.full_name}
              </Link>
              <span className="text-sm font-medium text-slate-700">
                {fmtMoneyMT(Number(p.amount))}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
