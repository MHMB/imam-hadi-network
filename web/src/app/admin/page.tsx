"use client";

import Link from "next/link";

import { KpiCard } from "@/components/ui/Card";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useKpi } from "@/lib/query/hooks";

export default function AdminLandingPage() {
  const kpi = useKpi();

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
