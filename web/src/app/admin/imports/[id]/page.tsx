"use client";

import { use } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { Card, KpiCard } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useImportPolling } from "@/lib/query/hooks";

const STATUS_LABEL: Record<string, string> = {
  pending: messages.importStatusPending,
  running: messages.importStatusRunning,
  success: messages.importStatusSuccess,
  failed: messages.importStatusFailed,
};

const STATUS_TONE: Record<string, "paid" | "unpaid" | "overdue"> = {
  pending: "unpaid",
  running: "unpaid",
  success: "paid",
  failed: "overdue",
};

export default function ImportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const importId = Number(id);
  const { data, isLoading, isError } = useImportPolling(
    Number.isFinite(importId) ? importId : null,
  );

  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState />;

  const report = data.report as Record<string, unknown>;
  const counts = {
    loans: report?.loans as number | undefined,
    persons: report?.persons as number | undefined,
    topics: report?.topics as number | undefined,
    issues: report?.issues as number | undefined,
  };

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <Link href="/admin/imports" className="text-sm text-slate-500 hover:text-slate-700">
          ← {messages.adminImports}
        </Link>
        <h1 className="break-all text-2xl font-bold text-slate-900 md:text-3xl">
          {data.source_filename}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <Badge tone={STATUS_TONE[data.status] ?? "unpaid"}>
            {STATUS_LABEL[data.status] ?? data.status}
          </Badge>
          <span>
            {messages.year}: {data.years_imported.map(toPersianDigits).join("، ")}
          </span>
          {data.duration_ms != null && <span>{toPersianDigits(data.duration_ms)} ms</span>}
        </div>
        <p className="break-all text-xs text-slate-400" title="sha256">
          {data.source_sha256}
        </p>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label={messages.kpiLoansTotal} value={toPersianDigits(counts.loans ?? 0)} />
        <KpiCard label={messages.kpiPersonsTotal} value={toPersianDigits(counts.persons ?? 0)} />
        <KpiCard label={messages.topic} value={toPersianDigits(counts.topics ?? 0)} />
        <KpiCard
          label={messages.adminIssues}
          value={toPersianDigits(counts.issues ?? 0)}
          tone={data.error_count > 0 ? "danger" : "default"}
          hint={`${messages.severityError}: ${toPersianDigits(data.error_count)}`}
        />
      </div>

      <Card>
        <Link
          href={`/admin/issues?import_id=${data.id}`}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-900 hover:underline"
        >
          {messages.adminIssues} →
        </Link>
        {data.error_message && (
          <p className="mt-3 rounded-md bg-overdue-subtle px-3 py-2 text-sm text-overdue">
            {data.error_message}
          </p>
        )}
      </Card>
    </section>
  );
}
