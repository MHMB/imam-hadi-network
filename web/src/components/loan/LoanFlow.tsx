"use client";

import { useMemo, useState } from "react";

import { Card } from "@/components/ui/Card";
import { toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import type { JalaliTriple } from "@/lib/jalali";
import { buildFlow, FLOW, type FlowLenderInput, type SegStatus } from "@/lib/loan-flow";

const num = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 3 });
const mt = (n: number) => `${num.format(n)} ${messages.flowMillionShort}`;
const trunc = (s: string, n = 18) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// Status is carried by stroke style as well as opacity, never by colour alone.
const BAND_STYLE: Record<SegStatus, { opacity: number; stroke?: string; dash?: string }> = {
  paid: { opacity: 0.45 },
  late: { opacity: 0.28, stroke: "#DC2626" },
  next: { opacity: 0.1, dash: "4 4" },
};
const PILL: Record<SegStatus, { bg: string; fg: string }> = {
  paid: { bg: "#DCFCE7", fg: "#166534" },
  late: { bg: "#DC2626", fg: "#FFFFFF" },
  next: { bg: "#F1F5F9", fg: "#334155" },
};

type Person = { id: number; full_name: string };

/**
 * One-glance picture of a loan: who funded it, who borrowed it, and how it is
 * repaid month by month. Read-only; the schedule tables below stay as the
 * accessible, exact view.
 */
export function LoanFlow({
  lenders,
  borrowers,
  guarantor,
  total,
  today,
}: {
  lenders: FlowLenderInput[];
  borrowers: Person[];
  guarantor: Person | null;
  total: number;
  today: JalaliTriple;
}) {
  const flow = useMemo(() => buildFlow(lenders, today), [lenders, today]);
  const [focus, setFocus] = useState<number | null>(null);
  if (lenders.length === 0) return null;

  const dim = (gi: number) => focus !== null && focus !== gi;
  const b = flow.borrower;
  const paid = flow.groups.reduce((acc, g) => acc + g.paid, 0);
  const late = flow.groups.reduce((acc, g) => acc + g.late, 0);
  const sched = flow.groups.reduce((acc, g) => acc + g.paid + g.remaining, 0) || 1;
  const barW = b.w - 48;
  const borrowerName =
    borrowers.length > 1
      ? `${trunc(borrowers[0].full_name, 14)} ${messages.flowAndMore} ${toPersianDigits(borrowers.length - 1)}`
      : trunc(borrowers[0]?.full_name ?? "—", 18);
  const lateMonths = flow.months.filter((m) => m.state === "late").length;
  const summary = `${flow.groups.length} ${messages.loanLenders}، ${mt(total)}؛ ${flow.months.length} ماه بازپرداخت، ${lateMonths} ماه معوق.`;

  return (
    <Card className="hidden md:block">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="flex-1 text-lg font-semibold text-slate-900">{messages.flowTitle}</h2>
        {flow.groups.length > 1 && (
          <div role="group" aria-label={messages.flowFilter} className="flex flex-wrap gap-1.5">
            {[null, ...flow.groups.map((_, i) => i)].map((gi) => {
              const g = gi === null ? null : flow.groups[gi];
              const on = focus === gi;
              return (
                <button
                  key={g?.key ?? "all"}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setFocus(gi)}
                  className={[
                    "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-xs font-medium",
                    on
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white text-slate-800 hover:border-slate-400",
                  ].join(" ")}
                >
                  <span
                    aria-hidden
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: g?.color ?? "#0F172A" }}
                  />
                  {g ? trunc(g.name, 14) : messages.flowAll}
                </button>
              );
            })}
          </div>
        )}
      </div>
      <p className="mb-2 mt-1 text-sm text-slate-600">{messages.flowHint}</p>

      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${flow.width} ${flow.height}`}
          className="block h-auto w-full min-w-[900px]"
          role="img"
          aria-label={summary}
          fontFamily="inherit"
          // RTL text: textAnchor "start" = the right edge, so mixed numbers read correctly.
          direction="rtl"
        >
          <text
            x={FLOW.lenderX + FLOW.lenderW}
            y={34}
            textAnchor="start"
            fontSize={13}
            fontWeight={700}
            fill="#334155"
          >
            {messages.loanLenders}
          </text>
          <text
            x={b.x + b.w / 2}
            y={34}
            textAnchor="middle"
            fontSize={13}
            fontWeight={700}
            fill="#334155"
          >
            {messages.borrower}
          </text>
          <text
            x={FLOW.monthX + FLOW.monthW}
            y={34}
            textAnchor="start"
            fontSize={13}
            fontWeight={700}
            fill="#334155"
          >
            {messages.flowRepayments}
          </text>

          {flow.inflows.map((band) => (
            <path
              key={`in-${band.group}`}
              d={band.d}
              fill={flow.groups[band.group].color}
              fillOpacity={focus === null ? 0.32 : focus === band.group ? 0.6 : 0.06}
            />
          ))}
          {flow.outflows.map((band, i) => {
            const st = BAND_STYLE[band.status ?? "next"];
            const color = flow.groups[band.group].color;
            const faded = dim(band.group);
            return (
              <path
                key={`out-${i}`}
                d={band.d}
                fill={color}
                fillOpacity={faded ? 0.04 : st.opacity}
                stroke={st.stroke ?? (st.dash ? color : "none")}
                strokeOpacity={faded ? 0.1 : 0.9}
                strokeWidth={1.5}
                strokeDasharray={st.dash}
              />
            );
          })}

          {flow.groups.map((g, gi) => {
            const node = (
              <g opacity={dim(gi) ? 0.3 : 1}>
                <rect
                  x={FLOW.lenderX}
                  y={g.y}
                  width={FLOW.lenderW}
                  height={g.h}
                  rx={12}
                  fill="#fff"
                  stroke={g.color}
                  strokeWidth={1.5}
                />
                <circle cx={FLOW.lenderX + FLOW.lenderW - 18} cy={g.y + 22} r={6} fill={g.color} />
                <text
                  x={FLOW.lenderX + FLOW.lenderW - 32}
                  y={g.y + 27}
                  textAnchor="start"
                  fontSize={14}
                  fontWeight={800}
                  fill="#0F172A"
                >
                  {g.personId === null
                    ? `${messages.flowOthers} (${toPersianDigits(g.members)} ${messages.flowPeople})`
                    : trunc(g.name)}
                </text>
                <text
                  x={FLOW.lenderX + FLOW.lenderW - 16}
                  y={g.y + 46}
                  textAnchor="start"
                  fontSize={12}
                  fill="#334155"
                >
                  {mt(g.amount)}، ٪{toPersianDigits(Math.round((g.amount / (total || 1)) * 100))}
                </text>
                {g.h >= 76 && (
                  <text
                    x={FLOW.lenderX + FLOW.lenderW - 16}
                    y={g.y + 66}
                    textAnchor="start"
                    fontSize={12}
                    fontWeight={g.late > 0 ? 700 : 400}
                    fill={g.late > 0 ? "#B91C1C" : g.remaining > 0 ? "#475569" : "#15803D"}
                  >
                    {g.late > 0
                      ? `${mt(g.late)} ${messages.overdue}`
                      : g.remaining > 0
                        ? `${mt(g.remaining)} ${messages.remaining}`
                        : messages.flowSettled}
                  </text>
                )}
              </g>
            );
            return g.personId === null ? (
              <g key={g.key}>{node}</g>
            ) : (
              <a key={g.key} href={`/persons/${g.personId}`} aria-label={g.name}>
                {node}
              </a>
            );
          })}

          <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={16} fill="#0F172A" />
          <text x={b.x + b.w / 2} y={b.y + 42} textAnchor="middle" fontSize={12} fill="#94A3B8">
            {messages.borrower}
          </text>
          <text
            x={b.x + b.w / 2}
            y={b.y + 70}
            textAnchor="middle"
            fontSize={15}
            fontWeight={800}
            fill="#fff"
          >
            {borrowerName}
          </text>
          <text
            x={b.x + b.w / 2}
            y={b.y + 136}
            textAnchor="middle"
            fontSize={34}
            fontWeight={800}
            fill="#fff"
          >
            {num.format(total)}
          </text>
          <text x={b.x + b.w / 2} y={b.y + 160} textAnchor="middle" fontSize={12} fill="#CBD5E1">
            میلیون تومان
          </text>
          {/* RTL progress: paid from the right, then late, then the rest */}
          <rect x={b.x + 24} y={b.y + 196} width={barW} height={8} rx={4} fill="#334155" />
          <rect
            x={b.x + 24 + barW * (1 - paid / sched)}
            y={b.y + 196}
            width={(barW * paid) / sched}
            height={8}
            rx={4}
            fill="#22C55E"
          />
          <rect
            x={b.x + 24 + barW * (1 - (paid + late) / sched)}
            y={b.y + 196}
            width={(barW * late) / sched}
            height={8}
            fill="#F87171"
          />
          <text x={b.x + b.w / 2} y={b.y + 230} textAnchor="middle" fontSize={12} fill="#E2E8F0">
            {mt(paid)} {messages.paid}
          </text>
          {late > 0 && (
            <text x={b.x + b.w / 2} y={b.y + 252} textAnchor="middle" fontSize={12} fill="#FCA5A5">
              {mt(late)} {messages.overdue}
            </text>
          )}

          {guarantor && (
            <a
              href={`/persons/${guarantor.id}`}
              aria-label={`${messages.guarantorLoan}: ${guarantor.full_name}`}
            >
              <line
                x1={b.x + b.w / 2}
                y1={b.y + b.h}
                x2={b.x + b.w / 2}
                y2={b.y + b.h + 16}
                stroke="#B45309"
                strokeWidth={2}
              />
              <rect
                x={b.x + 6}
                y={b.y + b.h + 16}
                width={b.w - 12}
                height={48}
                rx={12}
                fill="#FFFBEB"
                stroke="#B45309"
                strokeWidth={1.5}
              />
              <path
                d={`M${b.x + b.w - 20},${b.y + b.h + 26} l7,2.6 v5.2 c0,4.4 -7,7.4 -7,7.4 c0,0 -7,-3 -7,-7.4 v-5.2 z`}
                fill="none"
                stroke="#B45309"
                strokeWidth={1.6}
                strokeLinejoin="round"
              />
              <text
                x={b.x + b.w - 36}
                y={b.y + b.h + 36}
                textAnchor="start"
                fontSize={11}
                fontWeight={700}
                fill="#92400E"
              >
                {messages.guarantorLoan}
              </text>
              <text
                x={b.x + b.w - 36}
                y={b.y + b.h + 54}
                textAnchor="start"
                fontSize={13}
                fontWeight={800}
                fill="#78350F"
              >
                {trunc(guarantor.full_name, 16)}
              </text>
            </a>
          )}

          {flow.todayY !== null && (
            <g>
              <line
                x1={30}
                y1={flow.todayY}
                x2={FLOW.monthX + FLOW.monthW + 6}
                y2={flow.todayY}
                stroke="#0F172A"
                strokeWidth={1.5}
                strokeDasharray="5 4"
              />
              <rect
                x={FLOW.monthX + FLOW.monthW + 8}
                y={flow.todayY - 10}
                width={56}
                height={20}
                rx={10}
                fill="#0F172A"
              />
              <text
                x={FLOW.monthX + FLOW.monthW + 36}
                y={flow.todayY + 4}
                textAnchor="middle"
                fontSize={11}
                fontWeight={700}
                fill="#fff"
              >
                {messages.flowToday}
              </text>
            </g>
          )}

          {flow.months.map((m) => {
            const pill = PILL[m.state];
            const pillText =
              m.state === "paid"
                ? messages.flowPaidState
                : `${toPersianDigits(m.days)} ${m.state === "late" ? messages.flowDaysLate : messages.flowDaysLeft}`;
            const mid = m.y + m.h / 2;
            return (
              <g key={m.key}>
                <rect
                  x={FLOW.monthX}
                  y={m.y}
                  width={FLOW.monthW}
                  height={m.h}
                  rx={10}
                  fill={m.state === "late" ? "#FEF2F2" : "#FFFFFF"}
                  stroke={m.state === "late" ? "#FCA5A5" : "#E2E8F0"}
                />
                <text
                  x={FLOW.monthX + FLOW.monthW - 14}
                  y={mid - 3}
                  textAnchor="start"
                  fontSize={13}
                  fontWeight={700}
                  fill="#0F172A"
                >
                  {JALALI_MONTHS[m.jm - 1]} {toPersianDigits(m.jy)}
                </text>
                <text
                  x={FLOW.monthX + FLOW.monthW - 14}
                  y={mid + 14}
                  textAnchor="start"
                  fontSize={11}
                  fill="#475569"
                >
                  {mt(m.amount)}، {toPersianDigits(m.count)} {messages.flowInstallments}
                </text>
                <rect
                  x={FLOW.monthX + 10}
                  y={mid - 11}
                  width={98}
                  height={22}
                  rx={11}
                  fill={pill.bg}
                />
                <text
                  x={FLOW.monthX + 59}
                  y={mid + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={700}
                  fill={pill.fg}
                >
                  {pillText}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-700">
        <LegendSwatch className="bg-blue-600/50">{messages.flowLegendPaid}</LegendSwatch>
        <LegendSwatch className="border-[1.5px] border-red-600 bg-blue-600/25">
          {messages.flowLegendLate}
        </LegendSwatch>
        <LegendSwatch className="border-[1.5px] border-dashed border-blue-600 bg-blue-600/10">
          {messages.flowLegendNext}
        </LegendSwatch>
      </div>
    </Card>
  );
}

function LegendSwatch({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className={`inline-block h-2.5 w-5 rounded-sm ${className}`} />
      {children}
    </span>
  );
}
