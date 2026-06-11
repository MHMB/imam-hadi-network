"use client";

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

import { OverduePreview } from "@/components/home/OverduePreview";
import { Card, KpiCard } from "@/components/ui/Card";
import { ErrorState, Loading } from "@/components/ui/States";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { isFutureMonth, todayJalali } from "@/lib/jalali";
import { useCirculation, useKpi, useTopics } from "@/lib/query/hooks";

const PAID_COLOR = "#16a34a";
const UNPAID_COLOR = "#dc2626";
const SCHEDULED_COLOR = "#94a3b8"; // slate-400 — future months: not late, just not due yet
const YEAR_BAR_COLOR = "#0f172a";
const TOPIC_COLORS = [
  "#0f172a",
  "#16a34a",
  "#2563eb",
  "#d97706",
  "#dc2626",
  "#7c3aed",
  "#0d9488",
  "#be185d",
];
const TOPIC_SLICES = 7; // top topics shown individually; the rest fold into «سایر»

const fmtMoneyFromValue = (v: number | string | (string | number)[] | undefined): string =>
  fmtMoneyMT(Number(Array.isArray(v) ? v[0] : (v ?? 0)));

export default function HomePage() {
  const { data, isLoading, isError } = useKpi();
  const circulation = useCirculation();
  const topics = useTopics();
  const today = todayJalali();

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.appTitle}</h1>
      </header>

      {isLoading && <Loading />}
      {isError && <ErrorState />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiCard label={messages.kpiPersonsTotal} value={toPersianDigits(data.persons_total)} />
            <KpiCard
              label={messages.kpiLoansActive}
              value={toPersianDigits(data.loans_active)}
              hint={`${messages.kpiLoansTotal}: ${toPersianDigits(data.loans_total)}`}
            />
            <KpiCard
              label={messages.kpiOutstandingTotal}
              value={fmtMoneyMT(Number(data.outstanding_total))}
            />
            <KpiCard
              label={messages.kpiOverdue}
              value={toPersianDigits(data.overdue_installments)}
              tone={data.overdue_installments > 0 ? "danger" : "default"}
            />
          </div>

          <OverduePreview />

          {/* Monthly money circulation — whole history */}
          {circulation.data && circulation.data.months.length > 0 && (
            <Card>
              <h2 className="text-base font-semibold text-slate-900">{messages.homeCirculation}</h2>
              <p className="mb-3 mt-0.5 text-xs text-slate-500">{messages.homeCirculationHint}</p>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={circulation.data.months.map((m) => {
                      // Unpaid in a month that hasn't arrived yet is a
                      // scheduled installment, not an outstanding one —
                      // never paint the future red.
                      const future = isFutureMonth(m.persian_year, m.persian_month, today);
                      const unpaid = Number(m.amount_unpaid);
                      return {
                        label: m.label_fa,
                        paid: Number(m.amount_paid),
                        unpaid: future ? 0 : unpaid,
                        scheduled: future ? unpaid : 0,
                      };
                    })}
                    margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="label"
                      reversed
                      tick={{ fontSize: 10 }}
                      interval="preserveStartEnd"
                      minTickGap={24}
                    />
                    <YAxis tick={{ fontSize: 12 }} orientation="right" />
                    <Tooltip
                      formatter={(v, name) => [fmtMoneyFromValue(v as number), String(name)]}
                    />
                    <Legend />
                    <Bar dataKey="paid" stackId="amt" name={messages.paid} fill={PAID_COLOR} />
                    <Bar
                      dataKey="unpaid"
                      stackId="amt"
                      name={messages.remaining}
                      fill={UNPAID_COLOR}
                    />
                    <Bar
                      dataKey="scheduled"
                      stackId="amt"
                      name={messages.pending}
                      fill={SCHEDULED_COLOR}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* Borrowed-by-year bar + topic donut */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data.by_year.length > 0 && (
              <Card>
                <h2 className="mb-3 text-base font-semibold text-slate-900">
                  {messages.homeBorrowedByYear}
                </h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[...data.by_year]
                        .sort((a, b) => a.year - b.year)
                        .map((y) => ({
                          year: toPersianDigits(y.year),
                          total: Number(y.total),
                          outstanding: Number(y.outstanding),
                        }))}
                      margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="year" reversed tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} orientation="right" />
                      <Tooltip
                        formatter={(v, name) => [fmtMoneyFromValue(v as number), String(name)]}
                      />
                      <Legend />
                      <Bar dataKey="total" name={messages.loanTotal} fill={YEAR_BAR_COLOR} />
                      <Bar dataKey="outstanding" name={messages.remaining} fill={UNPAID_COLOR} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            {topics.data && topics.data.length > 0 && (
              <Card>
                <h2 className="mb-3 text-base font-semibold text-slate-900">
                  {messages.homeTopicDistribution}
                </h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={topicSlices(topics.data)}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={2}
                      >
                        {topicSlices(topics.data).map((slice, i) => (
                          <Cell key={slice.name} fill={TOPIC_COLORS[i % TOPIC_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v) => fmtMoneyFromValue(v as number)} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}
          </div>

          {data.by_year.length > 0 && (
            <section aria-labelledby="kpi-by-year">
              <h2 id="kpi-by-year" className="mb-3 text-lg font-semibold text-slate-900">
                {messages.kpiByYear}
              </h2>
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-4 py-2 text-start font-medium">{messages.year}</th>
                      <th className="px-4 py-2 text-start font-medium">{messages.kpiLoanCount}</th>
                      <th className="px-4 py-2 text-start font-medium">{messages.loanTotal}</th>
                      <th className="px-4 py-2 text-start font-medium">{messages.remaining}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.by_year.map((row) => (
                      <tr key={row.year}>
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {toPersianDigits(row.year)}
                        </td>
                        <td className="px-4 py-3">{toPersianDigits(row.loan_count)}</td>
                        <td className="px-4 py-3">{fmtMoneyMT(Number(row.total))}</td>
                        <td className="px-4 py-3">{fmtMoneyMT(Number(row.outstanding))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}

/** Top-N topics by total amount; the long tail folds into one «سایر» slice. */
function topicSlices(
  topics: { name: string; total: string | number; loan_count: number }[],
): { name: string; value: number }[] {
  const sorted = [...topics]
    .map((t) => ({ name: t.name, value: Number(t.total) }))
    .filter((t) => t.value > 0)
    .sort((a, b) => b.value - a.value);
  if (sorted.length <= TOPIC_SLICES + 1) return sorted;
  const head = sorted.slice(0, TOPIC_SLICES);
  const rest = sorted.slice(TOPIC_SLICES).reduce((acc, t) => acc + t.value, 0);
  return [...head, { name: "سایر", value: rest }];
}
