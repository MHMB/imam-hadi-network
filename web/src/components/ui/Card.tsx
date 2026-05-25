import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function KpiCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "danger" | "success";
}) {
  const valueClass = {
    default: "text-slate-900",
    danger: "text-overdue",
    success: "text-paid",
  }[tone];
  return (
    <Card>
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className={`mt-2 text-3xl font-bold leading-tight ${valueClass}`}>{value}</p>
      {hint != null && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  );
}
