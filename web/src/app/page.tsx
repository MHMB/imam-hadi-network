"use client";

import { KpiCard } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useKpi } from "@/lib/query/hooks";

export default function HomePage() {
  const { data, isLoading, isError } = useKpi();

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.appTitle}</h1>
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiCard label={messages.kpiPersonsTotal} value={toPersianDigits(data.persons_total)} />
            <KpiCard
              label={messages.kpiLoansActive}
              value={toPersianDigits(data.loans_active)}
              hint={`${messages.kpiLoansTotal}: ${toPersianDigits(data.loans_total)}`}
            />
            <KpiCard
              label={messages.kpiOutstandingTotal}
              value={fmtMoneyMT(Number(data.outstanding_total))}
            />
            <KpiCard
              label={messages.kpiOverdue}
              value={toPersianDigits(data.overdue_installments)}
              tone={data.overdue_installments > 0 ? "danger" : "default"}
            />
          </div>

          {data.by_year.length > 0 && (
            <section aria-labelledby="kpi-by-year">
              <h2 id="kpi-by-year" className="mb-3 text-lg font-semibold text-slate-900">
                {messages.kpiByYear}
              </h2>
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-4 py-2 text-start font-medium">{messages.year}</th>
                      <th className="px-4 py-2 text-start font-medium">{messages.kpiLoanCount}</th>
                      <th className="px-4 py-2 text-start font-medium">{messages.loanTotal}</th>
                      <th className="px-4 py-2 text-start font-medium">{messages.remaining}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.by_year.map((row) => (
                      <tr key={row.year}>
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {toPersianDigits(row.year)}
                        </td>
                        <td className="px-4 py-3">{toPersianDigits(row.loan_count)}</td>
                        <td className="px-4 py-3">{fmtMoneyMT(Number(row.total))}</td>
                        <td className="px-4 py-3">{fmtMoneyMT(Number(row.outstanding))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}
