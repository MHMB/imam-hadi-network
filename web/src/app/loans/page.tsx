"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { FilterChips } from "@/components/ui/FilterChips";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useLoans } from "@/lib/query/hooks";

type Status = "all" | "active" | "settled";

const PAGE_SIZE = 25;
const YEARS = [1404, 1405] as const;

export default function LoansPage() {
  const router = useRouter();
  const [year, setYear] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useLoans({
    year: year ?? undefined,
    status: status === "all" ? undefined : status,
    q: q || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.navLoans}</h1>
      </header>

      <div className="space-y-3">
        <input
          type="search"
          inputMode="search"
          placeholder={`${messages.loanNumber}...`}
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:border-slate-900 focus:outline-none"
          aria-label={messages.search}
        />
        <FilterChips<number | null>
          ariaLabel={messages.year}
          value={year}
          onChange={(v) => {
            setPage(1);
            setYear(v);
          }}
          options={[
            { value: null, label: messages.allYears },
            ...YEARS.map((y) => ({ value: y, label: toPersianDigits(y) })),
          ]}
        />
        <FilterChips<Status>
          value={status}
          onChange={(v) => {
            setPage(1);
            setStatus(v);
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
                  <th className="px-4 py-2 text-start font-medium">{messages.loanNumber}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.year}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.borrower}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.topic}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.loanTotal}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.remaining}</th>
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
