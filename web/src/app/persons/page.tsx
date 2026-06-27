"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { FilterBar, FilterSearch, FilterToggle } from "@/components/ui/filters";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { displayPhone, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { usePersons } from "@/lib/query/hooks";

const PAGE_SIZE = 25;

export default function PersonsPage() {
  const router = useRouter();
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

      <FilterBar>
        <FilterSearch
          value={q}
          onChange={(v) => {
            setPage(1);
            setQ(v);
          }}
          placeholder={messages.searchPlaceholder}
          ariaLabel={messages.search}
        />
        <FilterToggle
          active={verifiedOnly}
          onClick={() => {
            setPage(1);
            setVerifiedOnly((v) => !v);
          }}
        >
          {messages.verified}
        </FilterToggle>
        <FilterToggle
          active={hasDebt}
          onClick={() => {
            setPage(1);
            setHasDebt((v) => !v);
          }}
        >
          {messages.debtBalance}
        </FilterToggle>
        <FilterToggle
          active={hasReceivable}
          onClick={() => {
            setPage(1);
            setHasReceivable((v) => !v);
          }}
        >
          {messages.receivableBalance}
        </FilterToggle>
      </FilterBar>

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
                    {displayPhone(p.phone) && <span dir="ltr">{displayPhone(p.phone)}</span>}
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
                  <tr
                    key={p.id}
                    onClick={(e) => {
                      if (!(e.target as HTMLElement).closest("a")) router.push(`/persons/${p.id}`);
                    }}
                    className="cursor-pointer hover:bg-slate-50"
                  >
                    <td className="px-4 py-3 font-medium">
                      <Link href={`/persons/${p.id}`} className="text-slate-900 hover:underline">
                        {p.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600" dir="ltr">
                      {displayPhone(p.phone) ?? <span className="text-slate-300">—</span>}
                    </td>
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
