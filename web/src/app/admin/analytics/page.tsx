"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, KpiCard } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { useMonthlyAnalytics } from "@/lib/query/hooks";

const PAID_COLOR = "#16a34a"; // tailwind paid
const UNPAID_COLOR = "#dc2626"; // tailwind overdue
const TOPIC_BAR_COLOR = "#0f172a";

// Recharts tooltip formatters receive a ValueType union; we always feed
// number data, so coerce via String() defensively for the formatter sig.
const fmtMoneyFromValue = (v: number | string | (string | number)[] | undefined): string =>
  fmtMoneyMT(Number(Array.isArray(v) ? v[0] : (v ?? 0)));

export default function AdminAnalyticsPage() {
  const [override, setOverride] = useState<{ year: number; month: number } | null>(null);
  const { data, isLoading, isError } = useMonthlyAnalytics(override?.year, override?.month);

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.adminAnalytics}</h1>
        {data && <p className="mt-1 text-sm text-slate-600">{data.period.label_fa}</p>}
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiCard
              label={messages.monthlyDueCount}
              value={toPersianDigits(data.installments_due.count)}
            />
            <KpiCard
              label={messages.monthlyDueTotal}
              value={fmtMoneyMT(Number(data.installments_due.amount_total))}
            />
            <KpiCard
              label={messages.monthlyPaymentRate}
              value={`${toPersianDigits(Math.round(data.installments_due.payment_rate_pct))}٪`}
              tone={data.installments_due.payment_rate_pct >= 80 ? "success" : "default"}
            />
            <KpiCard
              label={messages.monthlyNewLoans}
              value={toPersianDigits(data.new_loans.count)}
              hint={`${messages.monthlyNewLoansTotal}: ${fmtMoneyMT(Number(data.new_loans.total_amount))}`}
            />
          </div>

          {/* Due-per-day stacked bar */}
          {data.installments_due.by_day.length > 0 && (
            <Card>
              <h2 className="mb-3 text-base font-semibold text-slate-900">
                {messages.monthlyDueByDay}
              </h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.installments_due.by_day.map((d) => ({
                      day: toPersianDigits(d.day),
                      paid: Number(d.paid_amount),
                      unpaid: Number(d.unpaid_amount),
                    }))}
                    margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="day" reversed tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} orientation="right" />
                    <Tooltip
                      formatter={(v, name) => [fmtMoneyFromValue(v as number), String(name)]}
                      labelFormatter={(l) => `${messages.dayOfMonth} ${l}`}
                    />
                    <Legend />
                    <Bar dataKey="paid" stackId="amt" name={messages.paid} fill={PAID_COLOR} />
                    <Bar
                      dataKey="unpaid"
                      stackId="amt"
                      name={messages.remaining}
                      fill={UNPAID_COLOR}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* Side-by-side: topic breakdown + donut */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data.new_loans_by_topic.length > 0 && (
              <Card>
                <h2 className="mb-3 text-base font-semibold text-slate-900">
                  {messages.monthlyByTopic}
                </h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={data.new_loans_by_topic.map((t) => ({
                        topic: t.topic_name,
                        total: Number(t.total),
                        count: t.count,
                      }))}
                      margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis type="number" tick={{ fontSize: 12 }} reversed />
                      <YAxis
                        dataKey="topic"
                        type="category"
                        tick={{ fontSize: 12 }}
                        orientation="right"
                        width={100}
                      />
                      <Tooltip
                        formatter={(v) => [fmtMoneyFromValue(v as number), messages.loanTotal]}
                      />
                      <Bar dataKey="total" fill={TOPIC_BAR_COLOR} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            <Card>
              <h2 className="mb-3 text-base font-semibold text-slate-900">
                {messages.monthlyPaymentRate}
              </h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        {
                          name: messages.paid,
                          value: Number(data.installments_due.amount_paid),
                        },
                        {
                          name: messages.remaining,
                          value: Number(data.installments_due.amount_unpaid),
                        },
                      ]}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={2}
                    >
                      <Cell fill={PAID_COLOR} />
                      <Cell fill={UNPAID_COLOR} />
                    </Pie>
                    <Tooltip formatter={(v) => fmtMoneyFromValue(v as number)} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          {/* Top borrowers + lenders */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <TopPersonsCard title={messages.monthlyTopBorrowers} items={data.top_borrowers} />
            <TopPersonsCard title={messages.monthlyTopLenders} items={data.top_lenders} />
          </div>
        </>
      )}

      {/* Quick month-jump (last 6 Jalali months relative to current period) */}
      {data && (
        <MonthPicker
          currentYear={data.period.persian_year}
          currentMonth={data.period.persian_month}
          onPick={(y, m) => setOverride({ year: y, month: m })}
        />
      )}
    </section>
  );
}

function TopPersonsCard({
  title,
  items,
}: {
  title: string;
  items: { person_id: number; full_name: string; total: string }[];
}) {
  return (
    <Card className="p-0">
      <div className="border-b border-slate-100 px-4 py-3">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        <p className="mt-0.5 text-xs text-slate-500">{messages.monthlyTopHint}</p>
      </div>
      {items.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-500">{messages.empty}</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((p) => (
            <li key={p.person_id} className="flex items-center justify-between px-4 py-2 text-sm">
              <Link href={`/persons/${p.person_id}`} className="text-slate-800 hover:underline">
                {p.full_name}
              </Link>
              <span className="font-medium text-slate-900">{fmtMoneyMT(Number(p.total))}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function MonthPicker({
  currentYear,
  currentMonth,
  onPick,
}: {
  currentYear: number;
  currentMonth: number;
  onPick: (year: number, month: number) => void;
}) {
  // Last 6 jalali months including the current view.
  const months: { y: number; m: number }[] = [];
  let y = currentYear;
  let m = currentMonth;
  for (let i = 0; i < 6; i++) {
    months.push({ y, m });
    m -= 1;
    if (m < 1) {
      m = 12;
      y -= 1;
    }
  }
  return (
    <Card>
      <h2 className="mb-3 text-sm font-medium text-slate-600">انتخاب ماه</h2>
      <div className="flex flex-wrap gap-2">
        {months.map(({ y, m }) => {
          const active = y === currentYear && m === currentMonth;
          return (
            <button
              key={`${y}-${m}`}
              type="button"
              onClick={() => onPick(y, m)}
              aria-pressed={active}
              className={[
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                active
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
              ].join(" ")}
            >
              {JALALI_MONTHS[m - 1]} {toPersianDigits(y)}
            </button>
          );
        })}
      </div>
    </Card>
  );
}
