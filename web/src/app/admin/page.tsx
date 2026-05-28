"use client";

import Link from "next/link";

import { Card, KpiCard } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useKpi, useOverdueInstallments } from "@/lib/query/hooks";

const TOP_OVERDUE = 5;

export default function AdminLandingPage() {
  const kpi = useKpi();
  const overdue = useOverdueInstallments({ page_size: TOP_OVERDUE });

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.adminLanding}</h1>
      </header>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard
          label={messages.kpiOverdue}
          value={kpi.data ? toPersianDigits(kpi.data.overdue_installments) : "—"}
          tone={kpi.data && kpi.data.overdue_installments > 0 ? "danger" : "default"}
        />
        <KpiCard
          label={messages.kpiOutstandingTotal}
          value={kpi.data ? fmtMoneyMT(Number(kpi.data.outstanding_total)) : "—"}
        />
        <KpiCard
          label={messages.kpiLoansActive}
          value={kpi.data ? toPersianDigits(kpi.data.loans_active) : "—"}
        />
        <KpiCard
          label={messages.kpiPersonsTotal}
          value={kpi.data ? toPersianDigits(kpi.data.persons_total) : "—"}
        />
      </div>

      {/* Top overdue panel */}
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

      {/* Quick links */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <AdminLinkCard href="/admin/overdue" title={messages.adminOverdue} />
        <AdminLinkCard href="/admin/analytics" title={messages.adminAnalytics} />
        <AdminLinkCard href="/admin/imports" title={messages.adminImports} />
        <AdminLinkCard href="/admin/issues" title={messages.adminIssues} />
      </section>
    </section>
  );
}

function AdminLinkCard({ href, title }: { href: string; title: string }) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-slate-200 bg-white p-4 text-sm font-medium text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-50"
    >
      {title} ←
    </Link>
  );
}
