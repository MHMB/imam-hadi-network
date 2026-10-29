"use client";

import Link from "next/link";
import { Suspense, useMemo } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { FilterBar, FilterSelect } from "@/components/ui/filters";
import { JalaliDatePicker } from "@/components/ui/JalaliDatePicker";
import { NoteBadge } from "@/components/ui/NoteBadge";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useKpi, useOverdueInstallments } from "@/lib/query/hooks";
import { useUrlParams } from "@/lib/url-params";

const PAGE_SIZE = 50;
const THRESHOLDS = [0, 30, 60, 90, 300, 600] as const;

export default function AdminOverduePage() {
  return (
    <Suspense fallback={<Loading />}>
      <OverdueInner />
    </Suspense>
  );
}

function OverdueInner() {
  const url = useUrlParams();
  const minDays = url.num("days") || 0;
  const year = url.num("year");
  const dueFrom = url.str("from");
  const dueTo = url.str("to");
  const page = url.num("page") || 1;
  const setFilter = (patch: Record<string, string | number | null>) =>
    url.set({ ...patch, page: null });

  const kpi = useKpi();
  const years = useMemo(
    () => (kpi.data ? [...kpi.data.by_year.map((y) => y.year)].sort((a, b) => b - a) : []),
    [kpi.data],
  );

  const { data, isLoading, isError } = useOverdueInstallments({
    min_days_overdue: minDays,
    year: year === "" ? undefined : year,
    due_from: dueFrom || undefined,
    due_to: dueTo || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  return (
    <section className="space-y-4">
      <header className="space-y-3">
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.adminOverdue}</h1>
        <FilterBar>
          <FilterSelect
            label={messages.year}
            value={String(year)}
            onChange={(v) => setFilter({ year: v })}
            options={[
              { value: "", label: messages.allYears },
              ...years.map((y) => ({ value: String(y), label: toPersianDigits(y) })),
            ]}
          />
          <JalaliDatePicker
            label={messages.dueFrom}
            value={dueFrom}
            onChange={(v) => setFilter({ from: v })}
          />
          <JalaliDatePicker
            label={messages.dueTo}
            value={dueTo}
            onChange={(v) => setFilter({ to: v })}
          />
          <FilterSelect
            label={messages.daysOverdue}
            value={String(minDays)}
            onChange={(v) => setFilter({ days: v === "0" ? null : v })}
            options={THRESHOLDS.map((t) => ({
              value: String(t),
              label: t === 0 ? messages.allItems : `+${toPersianDigits(t)} ${messages.days}`,
            }))}
          />
        </FilterBar>
        {data && (
          <p className="text-sm text-slate-600" role="status">
            {toPersianDigits(data.total)} {messages.kpiOverdueInstallmentsHint}
          </p>
        )}
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.items.length === 0 && <EmptyState />}
      {data && data.items.length > 0 && (
        <>
          {/* Mobile cards */}
          <ul className="space-y-2 md:hidden">
            {data.items.map((it) => (
              <li
                key={it.installment_id}
                className="rounded-lg border border-slate-200 bg-white p-3"
              >
                <div className="flex items-center justify-between">
                  <Link
                    href={`/loans/${it.loan_id}`}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    {messages.loanNumber} {toPersianDigits(it.loan_number)}
                  </Link>
                  {it.has_note && <NoteBadge />}
                  <Badge tone="overdue">
                    {toPersianDigits(it.days_overdue)} {messages.daysOverdue}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-slate-600">
                  {messages.borrower}: {it.borrower?.full_name ?? messages.noBorrower} ·{" "}
                  {messages.lender}: {it.lender.full_name}
                </div>
                <div className="mt-1 text-xs text-slate-700">
                  {fmtJalaliDate(it.due_persian_year, it.due_persian_month, it.due_day_of_month)} ·{" "}
                  {fmtMoneyMT(Number(it.amount))} · {it.topic_name}
                </div>
                {it.guarantor && (
                  <div className="mt-1 text-xs text-slate-500">
                    {messages.guarantorLoan}: {it.guarantor.full_name}
                  </div>
                )}
              </li>
            ))}
          </ul>
          {/* Desktop table */}
          <Card className="hidden p-0 md:block">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-2 text-start font-medium">{messages.loanNumber}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.borrower}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.lender}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.dueDate}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.loanTotal}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.daysOverdue}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.guarantorLoan}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((it) => (
                  <tr key={it.installment_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium">
                      <Link
                        href={`/loans/${it.loan_id}`}
                        className="text-slate-900 hover:underline"
                      >
                        {toPersianDigits(it.loan_number)}
                      </Link>
                      {it.has_note && (
                        <span className="ms-1.5 inline-block align-middle">
                          <NoteBadge />
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {it.borrower ? (
                        <Link
                          href={`/persons/${it.borrower.id}`}
                          className="text-slate-700 hover:underline"
                        >
                          {it.borrower.full_name}
                        </Link>
                      ) : (
                        <Badge tone="warning">{messages.noBorrower}</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/persons/${it.lender.id}`}
                        className="text-slate-700 hover:underline"
                      >
                        {it.lender.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      {fmtJalaliDate(
                        it.due_persian_year,
                        it.due_persian_month,
                        it.due_day_of_month,
                      )}
                    </td>
                    <td className="px-4 py-3">{fmtMoneyMT(Number(it.amount))}</td>
                    <td className="px-4 py-3">
                      <Badge tone="overdue">{toPersianDigits(it.days_overdue)}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {it.guarantor ? (
                        <Link href={`/persons/${it.guarantor.id}`} className="hover:underline">
                          {it.guarantor.full_name}
                        </Link>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onChange={(p) => url.set({ page: p === 1 ? null : p })}
          />
        </>
      )}
    </section>
  );
}
