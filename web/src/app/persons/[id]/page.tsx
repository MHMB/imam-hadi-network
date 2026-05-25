"use client";

import { use } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card, KpiCard } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { usePerson } from "@/lib/query/hooks";

const GUARANTOR_LABELS: Record<string, string> = {
  main: messages.guarantorMain,
  secondary_2: messages.guarantorSecondary2,
  secondary_3: messages.guarantorSecondary3,
  secondary_4: messages.guarantorSecondary4,
};

export default function PersonDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const personId = Number(id);
  const { data, isLoading, isError } = usePerson(Number.isFinite(personId) ? personId : null);

  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState />;

  const { person, guarantors, by_year, lifetime, upcoming, overdue } = data;

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <Link href="/persons" className="text-sm text-slate-500 hover:text-slate-700">
          ← {messages.navPeople}
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{person.full_name}</h1>
        <div className="flex flex-wrap gap-2 text-sm text-slate-600">
          <span>{person.phone}</span>
          {person.is_verified && <Badge tone="paid">{messages.verified}</Badge>}
        </div>
      </header>

      {/* Lifetime KPIs */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiCard
          label={messages.receivableBalance}
          value={fmtMoneyMT(Number(lifetime.receivable))}
        />
        <KpiCard label={messages.debtBalance} value={fmtMoneyMT(Number(lifetime.debt))} />
        <KpiCard
          label={messages.netCapital}
          value={fmtMoneyMT(Number(lifetime.net_capital))}
          tone={Number(lifetime.net_capital) >= 0 ? "success" : "danger"}
        />
      </div>

      {/* Guarantors */}
      {guarantors.length > 0 && (
        <Card>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">{messages.guarantorMain}</h2>
          <ul className="flex flex-wrap gap-2 text-sm">
            {guarantors.map((g) => (
              <li
                key={g.role}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5"
              >
                <Link href={`/persons/${g.person.id}`} className="text-slate-700 hover:underline">
                  {GUARANTOR_LABELS[g.role] ?? g.role}: <strong>{g.person.full_name}</strong>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Per-year breakdown */}
      {by_year.length > 0 && (
        <Card className="p-0">
          <h2 className="border-b border-slate-100 px-4 py-3 text-lg font-semibold text-slate-900">
            {messages.kpiByYear}
          </h2>
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{messages.year}</th>
                <th className="px-4 py-2 text-start font-medium">
                  {messages.borrower} ({messages.loan})
                </th>
                <th className="px-4 py-2 text-start font-medium">
                  {messages.lender} ({messages.amountLent})
                </th>
                <th className="px-4 py-2 text-start font-medium">{messages.remaining}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {by_year.map((y) => (
                <tr key={y.year}>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {toPersianDigits(y.year)}
                  </td>
                  <td className="px-4 py-3">
                    {toPersianDigits(y.as_borrower_loans)} ·{" "}
                    {fmtMoneyMT(Number(y.as_borrower_total))}
                  </td>
                  <td className="px-4 py-3">
                    {toPersianDigits(y.as_lender_parties)} · {fmtMoneyMT(Number(y.as_lender_total))}
                  </td>
                  <td className="px-4 py-3">
                    {fmtMoneyMT(Number(y.as_borrower_remaining) + Number(y.as_lender_remaining))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <InstallmentSection title={messages.overdue} tone="overdue" items={overdue} />
      <InstallmentSection title={messages.pending} tone="unpaid" items={upcoming} />
    </section>
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
      <h2 className="border-b border-slate-100 px-4 py-3 text-lg font-semibold text-slate-900">
        {title} ({toPersianDigits(items.length)})
      </h2>
      <ul className="divide-y divide-slate-100">
        {items.map((i, idx) => (
          <li
            key={`${i.loan_id}-${idx}`}
            className="flex items-center justify-between gap-3 px-4 py-3 text-sm"
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
