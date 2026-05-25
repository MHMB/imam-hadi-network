"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtJalaliDate, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useImports } from "@/lib/query/hooks";

const PAGE_SIZE = 20;

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

export default function AdminImportsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useImports({ page, page_size: PAGE_SIZE });

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.adminImports}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {messages.reimportFromExcel} — {messages.adminIssues}:{" "}
          <Link href="/admin/issues" className="text-slate-900 hover:underline">
            {messages.adminIssues}
          </Link>
        </p>
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.items.length === 0 && <EmptyState />}
      {data && data.items.length > 0 && (
        <>
          <Card className="p-0">
            <ul className="divide-y divide-slate-100">
              {data.items.map((imp) => {
                const ja = jalaliFromIso(imp.uploaded_at);
                return (
                  <li key={imp.id}>
                    <Link
                      href={`/admin/imports/${imp.id}`}
                      className="block px-4 py-3 hover:bg-slate-50"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-slate-900">{imp.source_filename}</span>
                        <Badge tone={STATUS_TONE[imp.status] ?? "unpaid"}>
                          {STATUS_LABEL[imp.status] ?? imp.status}
                        </Badge>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                        {ja && <span>{fmtJalaliDate(ja.year, ja.month, ja.day)}</span>}
                        <span>
                          {messages.year}: {imp.years_imported.map(toPersianDigits).join("، ")}
                        </span>
                        <span>
                          {messages.adminIssues}: {toPersianDigits(imp.issue_count)} (
                          {messages.severityError}: {toPersianDigits(imp.error_count)})
                        </span>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Card>
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}

// Tiny helper: convert ISO timestamp → Jalali triple via jalaali-js.
// Server returns UTC ISO; admins read it in local Jalali date.
import jalaali from "jalaali-js";

function jalaliFromIso(iso: string): { year: number; month: number; day: number } | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const j = jalaali.toJalaali(d.getFullYear(), d.getMonth() + 1, d.getDate());
  return { year: j.jy, month: j.jm, day: j.jd };
}
