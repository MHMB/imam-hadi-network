"use client";

import type { ReactNode } from "react";

/** Shared filter toolbar primitives — one inline, wrapping row across every
 * list page so filters never stack into full-width bands. */

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2">{children}</div>;
}

export function FilterSearch({
  value,
  onChange,
  placeholder,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  ariaLabel: string;
}) {
  return (
    <input
      type="search"
      inputMode="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={ariaLabel}
      className="h-10 min-w-[180px] flex-1 rounded-lg border border-slate-200 bg-white px-4 text-sm shadow-sm focus:border-slate-900 focus:outline-none"
    />
  );
}

export function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="relative inline-flex items-center">
      <span className="pointer-events-none absolute start-3 text-xs text-slate-400">{label}:</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        className="h-10 cursor-pointer rounded-lg border border-slate-200 bg-white pe-8 ps-14 text-sm text-slate-800 shadow-sm focus:border-slate-900 focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Boolean filter pill (verified / has-debt …). */
export function FilterToggle({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={[
        "h-10 rounded-lg border px-4 text-sm font-medium transition-colors",
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

/** Numeric filter with a leading label + trailing unit (e.g. "سررسید تا N روز"). */
export function FilterNumber({
  label,
  unit,
  value,
  onChange,
  min = 0,
  max,
  placeholder,
}: {
  label: string;
  unit?: string;
  value: number | "";
  onChange: (v: number | "") => void;
  min?: number;
  max?: number;
  placeholder?: string;
}) {
  return (
    <label className="inline-flex h-10 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-sm shadow-sm focus-within:border-slate-900">
      <span className="text-xs text-slate-400">{label}:</span>
      <input
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          const v = e.target.value;
          onChange(v === "" ? "" : Math.max(min, Number(v)));
        }}
        aria-label={label}
        className="w-14 bg-transparent text-center text-slate-800 focus:outline-none"
      />
      {unit && <span className="text-xs text-slate-400">{unit}</span>}
    </label>
  );
}
