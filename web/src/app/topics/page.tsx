"use client";

import { useMemo, useState } from "react";

import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useKpi, useTopics } from "@/lib/query/hooks";

type SortKey = "name" | "loan_count" | "total" | "paid" | "outstanding" | "pct";
type SortDir = "asc" | "desc";

type TopicRow = {
  id: number;
  name: string;
  loan_count: number;
  total: number;
  paid: number;
  outstanding: number;
  pct: number; // repaid percentage, 0..100
};

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "name", label: messages.topic, numeric: false },
  { key: "loan_count", label: messages.kpiLoanCount, numeric: true },
  { key: "total", label: messages.loanTotal, numeric: true },
  { key: "paid", label: messages.paid, numeric: true },
  { key: "outstanding", label: messages.remaining, numeric: true },
  { key: "pct", label: messages.topicsRepayment, numeric: true },
];

export default function TopicsPage() {
  const [year, setYear] = useState<number | undefined>(undefined);
  const [sortKey, setSortKey] = useState<SortKey>("total");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const { data, isLoading, isError } = useTopics(year);
  const kpi = useKpi();

  // Years come from the data itself (1401..1405 today, 1406 tomorrow).
  const years = useMemo(
    () => (kpi.data ? [...kpi.data.by_year.map((y) => y.year)].sort((a, b) => b - a) : []),
    [kpi.data],
  );

  const rows = useMemo<TopicRow[]>(() => {
    if (!data) return [];
    const mapped = data.map((t) => {
      const total = Number(t.total);
      const outstanding = Number(t.outstanding);
      const paid = Math.max(total - outstanding, 0);
      return {
        id: t.id,
        name: t.name,
        loan_count: t.loan_count,
        total,
        paid,
        outstanding,
        pct: total > 0 ? Math.round((paid / total) * 100) : 0,
      };
    });
    const dir = sortDir === "asc" ? 1 : -1;
    mapped.sort((a, b) => {
      if (sortKey === "name") return a.name.localeCompare(b.name, "fa") * dir;
      return (a[sortKey] - b[sortKey]) * dir;
    });
    return mapped;
  }, [data, sortKey, sortDir]);

  const onSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      // Text → alphabetical ascending; numbers → biggest first.
      setSortDir(key === "name" ? "asc" : "desc");
    }
  };

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.navTopics}</h1>
        <YearFilter years={years} year={year} onChange={setYear} />
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.length === 0 && <EmptyState />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.key} className="px-4 py-2 text-start font-medium">
                    <button
                      type="button"
                      onClick={() => onSort(col.key)}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                      aria-label={`${messages.sortedBy} ${col.label}`}
                      aria-pressed={sortKey === col.key}
                    >
                      {col.label}
                      <SortIndicator active={sortKey === col.key} dir={sortDir} />
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{t.name}</td>
                  <td className="px-4 py-3">{toPersianDigits(t.loan_count)}</td>
                  <td className="whitespace-nowrap px-4 py-3">{fmtMoneyMT(t.total)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-paid">{fmtMoneyMT(t.paid)}</td>
                  <td
                    className={`whitespace-nowrap px-4 py-3 ${
                      t.outstanding > 0 ? "text-slate-900" : "text-slate-400"
                    }`}
                  >
                    {fmtMoneyMT(t.outstanding)}
                  </td>
                  <td className="px-4 py-3">
                    <RepaymentBar pct={t.pct} hasLoans={t.loan_count > 0} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SortIndicator({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) {
    return (
      <span aria-hidden className="text-slate-300">
        ↕
      </span>
    );
  }
  return (
    <span aria-hidden className="text-slate-900">
      {dir === "asc" ? "↑" : "↓"}
    </span>
  );
}

/** Repaid share as a small bar + Persian percentage. */
function RepaymentBar({ pct, hasLoans }: { pct: number; hasLoans: boolean }) {
  if (!hasLoans) {
    return <span className="text-xs text-slate-400">—</span>;
  }
  return (
    <div className="flex min-w-28 items-center gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${pct >= 100 ? "bg-paid" : "bg-emerald-500"}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-slate-600">٪{toPersianDigits(pct)}</span>
    </div>
  );
}

function YearFilter({
  years,
  year,
  onChange,
}: {
  years: number[];
  year: number | undefined;
  onChange: (year: number | undefined) => void;
}) {
  return (
    <div role="group" className="flex flex-wrap gap-2" aria-label={messages.year}>
      <YearChip active={year === undefined} onClick={() => onChange(undefined)}>
        {messages.allYears}
      </YearChip>
      {years.map((y) => (
        <YearChip key={y} active={year === y} onClick={() => onChange(y)}>
          {toPersianDigits(y)}
        </YearChip>
      ))}
    </div>
  );
}

function YearChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
      ].join(" ")}
      aria-pressed={active}
    >
      {children}
    </button>
  );
}
