"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { usePersons } from "@/lib/query/hooks";

const PAGE_SIZE = 25;

export default function PersonsPage() {
  const [q, setQ] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [hasDebt, setHasDebt] = useState(false);
  const [hasReceivable, setHasReceivable] = useState(false);
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = usePersons({
    q: q || undefined,
    verified_only: verifiedOnly,
    has_debt: hasDebt,
    has_receivable: hasReceivable,
    page,
    page_size: PAGE_SIZE,
  });

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.navPeople}</h1>
      </header>

      <div className="space-y-3">
        <input
          type="search"
          inputMode="search"
          placeholder={messages.searchPlaceholder}
          value={q}
          onChange={(e) => {
            setPage(1);
            setQ(e.target.value);
          }}
          className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm shadow-sm focus:border-slate-900 focus:outline-none"
          aria-label={messages.search}
        />
        <div className="flex flex-wrap gap-2">
          <ToggleChip active={verifiedOnly} onClick={() => setVerifiedOnly((v) => !v)}>
            {messages.verified}
          </ToggleChip>
          <ToggleChip active={hasDebt} onClick={() => setHasDebt((v) => !v)}>
            {messages.debtBalance}
          </ToggleChip>
          <ToggleChip active={hasReceivable} onClick={() => setHasReceivable((v) => !v)}>
            {messages.receivableBalance}
          </ToggleChip>
        </div>
      </div>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.items.length === 0 && <EmptyState />}
      {data && data.items.length > 0 && (
        <>
          {/* Mobile: card list */}
          <ul className="space-y-2 md:hidden">
            {data.items.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/persons/${p.id}`}
                  className="block rounded-lg border border-slate-200 bg-white p-3 hover:border-slate-300"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-900">{p.full_name}</span>
                    {p.is_verified && <Badge tone="paid">{messages.verified}</Badge>}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500">
                    <span>{p.phone}</span>
                    <span>
                      {messages.netCapital}: {fmtMoneyMT(Number(p.net_capital))}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {/* Desktop: table */}
          <Card className="hidden p-0 md:block">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-2 text-start font-medium">{messages.fullName}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.phone}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.amountLent}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.amountBorrowed}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.netCapital}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.verified}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium">
                      <Link href={`/persons/${p.id}`} className="text-slate-900 hover:underline">
                        {p.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{p.phone}</td>
                    <td className="px-4 py-3">{fmtMoneyMT(Number(p.total_lent))}</td>
                    <td className="px-4 py-3">{fmtMoneyMT(Number(p.total_borrowed))}</td>
                    <td className="px-4 py-3 font-medium">{fmtMoneyMT(Number(p.net_capital))}</td>
                    <td className="px-4 py-3">
                      {p.is_verified ? (
                        <Badge tone="paid">{toPersianDigits("✓")}</Badge>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
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

function ToggleChip({
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
      aria-pressed={active}
      className={[
        "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
      ].join(" ")}
    >
      {children}
    </button>
  );
}
