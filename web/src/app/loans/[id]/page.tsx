"use client";

import { use } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { isPastDue, todayJalali } from "@/lib/jalali";
import { useLoan } from "@/lib/query/hooks";

export default function LoanDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const loanId = Number(id);
  const { data, isLoading, isError } = useLoan(Number.isFinite(loanId) ? loanId : null);
  const today = todayJalali();

  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState />;

  const { loan, topic, guarantor, borrowers, lenders, totals } = data;

  // The OpenAPI codegen typed `loan` as a free-form dict; pull out the fields
  // we render so the JSX stays readable.
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

      <section aria-labelledby="lenders" className="space-y-3">
        <h2 id="lenders" className="text-lg font-semibold text-slate-900">
          {messages.lenders} ({toPersianDigits(lenders.length)})
        </h2>
        <div className="space-y-3">
          {lenders.map((ln) => (
            <Card key={ln.party_id} className="p-0">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 px-4 py-3">
                <Link
                  href={`/persons/${ln.person.id}`}
                  className="font-medium text-slate-900 hover:underline"
                >
                  {ln.person.full_name}
                </Link>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                  <span>
                    {messages.amountLent}: {fmtMoneyMT(Number(ln.amount))}
                  </span>
                  <span>
                    {messages.paid}: {fmtMoneyMT(Number(ln.paid))}
                  </span>
                  <span>
                    {messages.remaining}: {fmtMoneyMT(Number(ln.remaining))}
                  </span>
                </div>
              </div>
              {ln.installments.length > 0 ? (
                <ul className="divide-y divide-slate-100 text-sm">
                  {ln.installments.map((inst, idx) => (
                    <li
                      key={idx}
                      className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5"
                    >
                      <span className="text-slate-600">
                        {JALALI_MONTHS[inst.due_persian_month - 1]}
                      </span>
                      <span className="text-slate-700">
                        {fmtJalaliDate(
                          inst.due_persian_year,
                          inst.due_persian_month,
                          inst.due_day_of_month,
                        )}
                      </span>
                      <span className="font-medium text-slate-900">
                        {fmtMoneyMT(Number(inst.amount))}
                      </span>
                      <InstallmentBadge
                        status={inst.status}
                        overdue={isPastDue(
                          inst.due_persian_year,
                          inst.due_persian_month,
                          inst.due_day_of_month,
                          today,
                        )}
                      />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-4 py-3 text-sm text-slate-500">{messages.empty}</p>
              )}
            </Card>
          ))}
        </div>
      </section>
    </section>
  );
}

/** DESIGN §6.3 status badges: paid → green, unpaid past-due → red «معوق»,
 * unpaid future → neutral «در انتظار». */
function InstallmentBadge({ status, overdue }: { status: string; overdue: boolean }) {
  if (status === "paid") {
    return <Badge tone="paid">{messages.paid}</Badge>;
  }
  if (overdue) {
    return <Badge tone="overdue">{messages.overdue}</Badge>;
  }
  return <Badge tone="unpaid">{messages.pending}</Badge>;
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-base font-bold text-slate-900">{value}</p>
    </div>
  );
}

function PartySection({
  title,
  items,
}: {
  title: string;
  items: NonNullable<ReturnType<typeof useLoan>["data"]>["borrowers"];
}) {
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
