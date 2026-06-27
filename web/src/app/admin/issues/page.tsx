"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { FilterSelect } from "@/components/ui/filters";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { toPersianDigits } from "@/lib/format";
import { categoryLabel, messages, severityLabel } from "@/lib/i18n";
import { useIssues } from "@/lib/query/hooks";

type Severity = "error" | "warning" | "info";

const PAGE_SIZE = 50;
const SEVERITIES: Severity[] = ["error", "warning", "info"];

export default function AdminIssuesPage() {
  return (
    <Suspense fallback={<Loading />}>
      <IssuesInner />
    </Suspense>
  );
}

function IssuesInner() {
  const search = useSearchParams();
  const importIdParam = search.get("import_id");
  const importId = importIdParam ? Number(importIdParam) : undefined;

  const [severity, setSeverity] = useState<Severity | null>(null);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useIssues({
    import_id: importId,
    severity: severity ?? undefined,
    page,
    page_size: PAGE_SIZE,
  });

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.adminIssues}</h1>
        {importId != null && (
          <p className="mt-1 text-sm text-slate-600">
            <Link href={`/admin/imports/${importId}`} className="text-slate-900 hover:underline">
              ← {messages.adminImports} #{toPersianDigits(importId)}
            </Link>
          </p>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <FilterSelect
          label={messages.severityLabel}
          value={severity ?? ""}
          onChange={(v) => {
            setPage(1);
            setSeverity(v === "" ? null : (v as Severity));
          }}
          options={[
            { value: "", label: messages.allSeverities },
            ...SEVERITIES.map((s) => ({ value: s, label: severityLabel(s) })),
          ]}
        />
      </div>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.items.length === 0 && <EmptyState />}
      {data && data.items.length > 0 && (
        <>
          <Card className="p-0">
            <ul className="divide-y divide-slate-100">
              {data.items.map((it) => (
                <li key={it.id} className="space-y-1 px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={severityTone(it.severity)}>{severityLabel(it.severity)}</Badge>
                    <Badge tone="neutral">{categoryLabel(it.category)}</Badge>
                    {it.cell && (
                      <button
                        type="button"
                        onClick={() => navigator.clipboard?.writeText(it.cell ?? "")}
                        className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700 hover:bg-slate-200"
                        title="کپی به کلیپ‌بورد"
                      >
                        {it.cell}
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-slate-800">{it.message}</p>
                </li>
              ))}
            </ul>
          </Card>
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}

function severityTone(s: string): "overdue" | "unpaid" | "neutral" {
  if (s === "error") return "overdue";
  if (s === "warning") return "unpaid";
  return "neutral";
}
