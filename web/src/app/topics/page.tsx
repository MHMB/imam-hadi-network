"use client";

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useTopics } from "@/lib/query/hooks";

const YEARS = [1404, 1405] as const;

export default function TopicsPage() {
  const [year, setYear] = useState<number | undefined>(undefined);
  const { data, isLoading, isError } = useTopics(year);

  return (
    <section className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.navTopics}</h1>
        <YearFilter year={year} onChange={setYear} />
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && data.length === 0 && <EmptyState />}
      {data && data.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-slate-100">
            {data.map((topic) => (
              <li
                key={topic.id}
                className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="text-sm font-medium text-slate-900">{topic.name}</span>
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-slate-600">
                  <span>
                    {messages.kpiLoanCount}: {toPersianDigits(topic.loan_count)}
                  </span>
                  <span>
                    {messages.loanTotal}: {fmtMoneyMT(Number(topic.total))}
                  </span>
                  <span>
                    {messages.remaining}: {fmtMoneyMT(Number(topic.outstanding))}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}

function YearFilter({
  year,
  onChange,
}: {
  year: number | undefined;
  onChange: (year: number | undefined) => void;
}) {
  return (
    <div role="group" className="flex flex-wrap gap-2" aria-label={messages.year}>
      <YearChip active={year === undefined} onClick={() => onChange(undefined)}>
        {messages.allYears}
      </YearChip>
      {YEARS.map((y) => (
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
