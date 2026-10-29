"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { FilterBar, FilterSearch, FilterSelect, FilterToggle } from "@/components/ui/filters";
import { Pagination } from "@/components/ui/Pagination";
import { type SortDir, SortableTh } from "@/components/ui/SortableTh";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { displayPhone, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useGuarantorOptions, usePersons } from "@/lib/query/hooks";
import { useUrlParams } from "@/lib/url-params";

const PAGE_SIZE = 25;
type SortKey = "name" | "lent" | "borrowed" | "net" | "overdue";
const SORT_KEYS: readonly SortKey[] = ["name", "lent", "borrowed", "net", "overdue"];

export default function PersonsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <PersonsInner />
    </Suspense>
  );
}

function VerifiedMark() {
  return (
    <span
      title={messages.verified}
      aria-label={messages.verified}
      role="img"
      className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-paid text-[10px] text-white"
    >
      ✓
    </span>
  );
}

function PersonsInner() {
  const router = useRouter();
  const url = useUrlParams();
  const q = url.str("q");
  const verifiedOnly = url.str("verified") === "1";
  const hasDebt = url.str("debt") === "1";
  const hasReceivable = url.str("receivable") === "1";
  const guarantorId = url.num("guarantor");
  const sortParam = url.str("sort") as SortKey;
  const sortKey: SortKey = SORT_KEYS.includes(sortParam) ? sortParam : "name";
  const sortDir: SortDir = url.str("dir") === "desc" ? "desc" : "asc";
  const page = url.num("page") || 1;
  const setFilter = (patch: Record<string, string | number | null>) =>
    url.set({ ...patch, page: null });
  const toggle = (key: string, on: boolean) => setFilter({ [key]: on ? null : "1" });

  const guarantors = useGuarantorOptions();
  const { data, isLoading, isError } = usePersons({
    q: q || undefined,
    verified_only: verifiedOnly,
    has_debt: hasDebt,
    has_receivable: hasReceivable,
    guarantor_id: guarantorId === "" ? undefined : guarantorId,
    sort: sortKey,
    sort_dir: sortDir,
    page,
    page_size: PAGE_SIZE,
  });

  // Money columns open largest-first; name opens A→Z.
  const onSort = (key: SortKey) => {
    const dir: SortDir =
      key === sortKey ? (sortDir === "asc" ? "desc" : "asc") : key === "name" ? "asc" : "desc";
    setFilter({
      sort: key === "name" && dir === "asc" ? null : key,
      dir: dir === "asc" ? null : dir,
    });
  };
  const th = (label: string, key: SortKey) => (
    <SortableTh label={label} sortKey={key} active={sortKey} dir={sortDir} onSort={onSort} />
  );

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.navPeople}</h1>
      </header>

      <FilterBar>
        <FilterSearch
          value={q}
          onChange={(v) => setFilter({ q: v })}
          placeholder={messages.searchPlaceholder}
          ariaLabel={messages.search}
        />
        <FilterSelect
          label={messages.memberGuarantor}
          value={String(guarantorId)}
          onChange={(v) => setFilter({ guarantor: v })}
          options={[
            { value: "", label: messages.allItems },
            ...(guarantors.data ?? []).map((g) => ({
              value: String(g.id),
              label: `${g.full_name} (${toPersianDigits(g.members)})`,
            })),
          ]}
        />
        <FilterToggle active={hasDebt} onClick={() => toggle("debt", hasDebt)}>
          {messages.debtBalance}
        </FilterToggle>
        <FilterToggle active={hasReceivable} onClick={() => toggle("receivable", hasReceivable)}>
          {messages.receivableBalance}
        </FilterToggle>
        <FilterToggle active={verifiedOnly} onClick={() => toggle("verified", verifiedOnly)}>
          {messages.verified}
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
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 font-medium text-slate-900">
                      {p.full_name}
                      {p.is_verified && <VerifiedMark />}
                    </span>
                    {Number(p.overdue_debt) > 0 && (
                      <Badge tone="overdue">{fmtMoneyMT(Number(p.overdue_debt))}</Badge>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500">
                    {p.guarantor && (
                      <span>
                        {messages.memberGuarantor}: {p.guarantor.full_name}
                      </span>
                    )}
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
          <Card className="hidden overflow-x-auto p-0 md:block">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  {th(messages.fullName, "name")}
                  <th className="px-4 py-2 text-start font-medium">{messages.memberGuarantor}</th>
                  <th className="px-4 py-2 text-start font-medium">{messages.phone}</th>
                  {th(messages.amountLent, "lent")}
                  {th(messages.amountBorrowed, "borrowed")}
                  {th(messages.netCapital, "net")}
                  {th(messages.overdueTotal, "overdue")}
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
                      <span className="inline-flex items-center gap-1.5">
                        <Link href={`/persons/${p.id}`} className="text-slate-900 hover:underline">
                          {p.full_name}
                        </Link>
                        {p.is_verified && <VerifiedMark />}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {p.guarantor ? (
                        <Link href={`/persons/${p.guarantor.id}`} className="hover:underline">
                          {p.guarantor.full_name}
                        </Link>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600" dir="ltr">
                      {displayPhone(p.phone) ?? <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-4 py-3">{fmtMoneyMT(Number(p.total_lent))}</td>
                    <td className="px-4 py-3">{fmtMoneyMT(Number(p.total_borrowed))}</td>
                    <td className="px-4 py-3 font-medium">{fmtMoneyMT(Number(p.net_capital))}</td>
                    <td className="px-4 py-3">
                      {Number(p.overdue_debt) > 0 ? (
                        <span className="font-semibold text-overdue">
                          {fmtMoneyMT(Number(p.overdue_debt))}
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onChange={(p) => url.set({ page: p === 1 ? null : p })}
          />
        </>
      )}
    </section>
  );
}
