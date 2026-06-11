"use client";

import Link from "next/link";

import { Card } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useOverdueInstallments } from "@/lib/query/hooks";

const TOP_OVERDUE = 5;

/** Worst-N overdue installments — shown on the home page, links to the
 * full /admin/overdue listing. */
export function OverduePreview() {
  const overdue = useOverdueInstallments({ page_size: TOP_OVERDUE });

  return (
    <section aria-labelledby="top-overdue">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="top-overdue" className="text-lg font-semibold text-slate-900">
          {messages.adminOverdue}
        </h2>
        <Link href="/admin/overdue" className="text-sm text-slate-700 hover:underline">
          مشاهده همه ←
        </Link>
      </div>
      {overdue.isLoading && <Loading />}
      {overdue.isError && <ErrorState />}
      {overdue.data && overdue.data.items.length === 0 && (
        <Card>
          <p className="py-4 text-center text-sm text-slate-500">{messages.empty}</p>
        </Card>
      )}
      {overdue.data && overdue.data.items.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-slate-100">
            {overdue.data.items.map((it) => (
              <li key={it.installment_id} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link
                    href={`/loans/${it.loan_id}`}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    {messages.loanNumber} {toPersianDigits(it.loan_number)}
                  </Link>
                  <span className="font-semibold text-overdue">
                    {toPersianDigits(it.days_overdue)} {messages.daysOverdue}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-600">
                  <span>
                    {messages.borrower}: {it.borrower.full_name}
                  </span>
                  <span>
                    {messages.lender}: {it.lender.full_name}
                  </span>
                  <span>{fmtMoneyMT(Number(it.amount))}</span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}
