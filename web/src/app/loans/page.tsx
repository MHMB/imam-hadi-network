"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useKpi, useLoans } from "@/lib/query/hooks";

type Status = "all" | "active" | "settled";
type SortKey = "loan_number" | "year" | "total" | "remaining";
type SortDir = "asc" | "desc";

const PAGE_SIZE = 25;

export default function LoansPage() {
  const router = useRouter();
  const [year, setYear] = useState<number | "">("");
  const [status, setStatus] = useState<Status>("all");
  const [q, setQ] = useState("");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);

  const kpi = useKpi();
  const years = useMemo(
    () => (kpi.data ? [...kpi.data.by_year.map((y) => y.year)].sort((a, b) => b - a) : []),
    [kpi.data],
  );

  const { data, isLoading, isError } = useLoans({
    year: year === "" ? undefined : year,
    status: status === "all" ? undefined : status,
    q: q || undefined,
    sort: sortKey ?? undefined,
    sort_dir: sortKey ? sortDir : undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const onSort = (key: SortKey) => {
    setPage(1);
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "total" || key === "remaining" ? "desc" : "asc");
    }
  };

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.navLoans}</h1>
      </header>

      {/* Single filter toolbar — search grows, selects sit inline and wrap */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          inputMode="search"
          placeholder={`${messages.loanNumber}...`}
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          className="h-10 min-w-[180px] flex-1 rounded-lg border border-slate-200 bg-white px-4 text-sm shadow-sm focus:border-slate-900 focus:outline-none"
          aria-label={messages.search}
        />
        <FilterSelect
          label={messages.year}
          value={String(year)}
          onChange={(v) => {
            setPage(1);
            setYear(v === "" ? "" : Number(v));
          }}
          options={[
            { value: "", label: messages.allYears },
            ...years.map((y) => ({ value: String(y), label: toPersianDigits(y) })),
          ]}
        />
        <FilterSelect
          label={messages.statusLabel}
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v as Status);
          }}
          options={[
            { value: "all", label: messages.allStatuses },
            { value: "active", label: messages.active },
            { value: "settled", label: messages.settled },
          ]}
        />
      </div>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.items.length === 0 && <EmptyState />}
      {data && data.items.length > 0 && (
        <>
          {/* Mobile cards */}
          <ul className="space-y-2 md:hidden">
            {data.items.map((ln) => (
              <li key={ln.id}>
                <Link
                  href={`/loans/${ln.id}`}
                  className="block rounded-lg border border-slate-200 bg-white p-3 hover:border-slate-300"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-900">
                      {messages.loanNumber} {toPersianDigits(ln.loan_number)}
                    </span>
                    <Badge tone={ln.status}>
                      {ln.status === "active" ? messages.active : messages.settled}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {toPersianDigits(ln.persian_year)} · {ln.topic_name} · {messages.borrower}:{" "}
                    {ln.borrower_name}
                  </div>
                  <div className="mt-1 text-xs text-slate-700">
                    {fmtMoneyMT(Number(ln.total))} · {messages.remaining}{" "}
                    {fmtMoneyMT(Number(ln.remaining))}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {/* Desktop table */}
          <Card className="hidden p-0 md:block">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <SortableTh
                    label={messages.loanNumber}
                    sortKey="loan_number"
                    active={sortKey}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <SortableTh
                    label={messages.year}
                    sortKey="year"
                    active={sortKey}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <th className="px-4 py-2 text-start font-medium">{messages.borrower}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.topic}</th>
                  <SortableTh
                    label={messages.loanTotal}
                    sortKey="total"
                    active={sortKey}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <SortableTh
                    label={messages.remaining}
                    sortKey="remaining"
                    active={sortKey}
                    dir={sortDir}
                    onSort={onSort}
                  />
                  <th className="px-4 py-2 text-start font-medium">{messages.active}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((ln) => (
                  <tr
                    key={ln.id}
                    onClick={(e) => {
                      if (!(e.target as HTMLElement).closest("a")) router.push(`/loans/${ln.id}`);
                    }}
                    className="cursor-pointer hover:bg-slate-50"
                  >
                    <td className="px-4 py-3 font-medium">
                      <Link href={`/loans/${ln.id}`} className="text-slate-900 hover:underline">
                        {toPersianDigits(ln.loan_number)}
                      </Link>
                    </td>
                    <td className="px-4 py-3">{toPersianDigits(ln.persian_year)}</td>
                    <td className="px-4 py-3">{ln.borrower_name}</td>
                    <td className="px-4 py-3">{ln.topic_name}</td>
                    <td className="px-4 py-3">{fmtMoneyMT(Number(ln.total))}</td>
                    <td className="px-4 py-3 font-medium">{fmtMoneyMT(Number(ln.remaining))}</td>
                    <td className="px-4 py-3">
                      <Badge tone={ln.status}>
                        {ln.status === "active" ? messages.active : messages.settled}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}

function SortableTh({
  label,
  sortKey,
  active,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  active: SortKey | null;
  dir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const isActive = active === sortKey;
  return (
    <th className="px-4 py-2 text-start font-medium">
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        aria-pressed={isActive}
        aria-label={`${messages.sortedBy} ${label}`}
        className="inline-flex items-center gap-1 hover:text-slate-900"
      >
        {label}
        <span aria-hidden className={isActive ? "text-slate-900" : "text-slate-300"}>
          {isActive ? (dir === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="relative inline-flex items-center">
      <span className="pointer-events-none absolute start-3 text-xs text-slate-400">{label}:</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        className="h-10 cursor-pointer rounded-lg border border-slate-200 bg-white pe-8 ps-14 text-sm text-slate-800 shadow-sm focus:border-slate-900 focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
