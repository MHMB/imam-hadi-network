"use client";

import type { ReactNode } from "react";

export interface ChipOption<T extends string | number | null> {
  value: T;
  label: ReactNode;
}

export function FilterChips<T extends string | number | null>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: ChipOption<T>[];
  value: T;
  onChange: (v: T) => void;
  ariaLabel?: string;
}) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            type="button"
            onClick={() => onChange(opt.value)}
            className={[
              "rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
            ].join(" ")}
            aria-pressed={active}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
