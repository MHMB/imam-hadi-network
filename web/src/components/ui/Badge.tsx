import type { ReactNode } from "react";

type Tone = "paid" | "unpaid" | "overdue" | "active" | "settled" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  paid: "bg-paid-subtle text-paid",
  settled: "border border-paid text-paid",
  unpaid: "bg-unpaid-subtle text-unpaid",
  active: "bg-unpaid-subtle text-unpaid",
  overdue: "bg-overdue-subtle text-overdue",
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
