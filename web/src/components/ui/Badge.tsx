import type { ReactNode } from "react";

import { messages } from "@/lib/i18n";

type Tone = "paid" | "unpaid" | "overdue" | "active" | "settled" | "warning" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  paid: "bg-paid-subtle text-paid",
  settled: "border border-paid text-paid",
  unpaid: "bg-unpaid-subtle text-unpaid",
  active: "bg-unpaid-subtle text-unpaid",
  overdue: "bg-overdue-subtle text-overdue",
  warning: "bg-amber-50 text-amber-900 border border-amber-300",
  neutral: "bg-slate-100 text-slate-700",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

/** Loan state chip: settled, or active — and «معوق» (with a clock, not colour
 * alone) when an installment is past due. */
export function LoanStatusBadge({ settled, overdue }: { settled: boolean; overdue: boolean }) {
  if (settled) return <Badge tone="settled">{messages.settled}</Badge>;
  if (!overdue) return <Badge tone="active">{messages.active}</Badge>;
  return (
    <Badge tone="overdue">
      <svg
        className="me-1 h-3.5 w-3.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        aria-hidden
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
      {messages.overdue}
    </Badge>
  );
}
