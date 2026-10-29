"use client";

import jalaali from "jalaali-js";
import { useEffect, useRef, useState } from "react";

import { toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { todayJalali } from "@/lib/jalali";

const WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]; // Saturday first

/** "1405-07-01" ⇄ {jy, jm, jd}; empty string = no date. */
export function parseJalali(value: string): { jy: number; jm: number; jd: number } | null {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value);
  if (!m) return null;
  const [jy, jm, jd] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return jalaali.isValidJalaaliDate(jy, jm, jd) ? { jy, jm, jd } : null;
}
export const formatJalaliValue = (jy: number, jm: number, jd: number) =>
  `${jy}-${String(jm).padStart(2, "0")}-${String(jd).padStart(2, "0")}`;

/** Weekday column (0 = Saturday) of the first day of a Jalali month. */
function firstColumn(jy: number, jm: number): number {
  const g = jalaali.toGregorian(jy, jm, 1);
  return (new Date(g.gy, g.gm - 1, g.gd).getDay() + 1) % 7;
}

/**
 * Filter-sized Jalali date control: a button that opens a month calendar.
 * Value is `YYYY-MM-DD` (Jalali) or "" — the shape the API filters take.
 */
export function JalaliDatePicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const selected = parseJalali(value);
  const today = todayJalali();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => ({
    jy: selected?.jy ?? today.jy,
    jm: selected?.jm ?? today.jm,
  }));
  const root = useRef<HTMLDivElement>(null);

  // Close when clicking anywhere outside the control.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const shift = (delta: number) =>
    setView(({ jy, jm }) => {
      const i = jy * 12 + (jm - 1) + delta;
      return { jy: Math.floor(i / 12), jm: (i % 12) + 1 };
    });

  const days = jalaali.jalaaliMonthLength(view.jy, view.jm);
  const lead = firstColumn(view.jy, view.jm);
  const shown = selected
    ? `${toPersianDigits(selected.jd)} ${JALALI_MONTHS[selected.jm - 1]} ${toPersianDigits(selected.jy)}`
    : "—";

  return (
    <div
      ref={root}
      className="relative inline-flex"
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          if (!open && selected) setView({ jy: selected.jy, jm: selected.jm });
          setOpen((o) => !o);
        }}
        className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white pe-3 ps-3 text-sm text-slate-800 shadow-sm hover:border-slate-300 focus:border-slate-900 focus:outline-none"
      >
        <svg
          className="h-4 w-4 text-slate-500"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          aria-hidden
        >
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M3 10h18M8 3v4M16 3v4" />
        </svg>
        <span className="text-xs text-slate-400">{label}:</span>
        <span>{shown}</span>
      </button>
      {selected && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label={`${messages.clear} ${label}`}
          className="ms-1 inline-flex h-10 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
        >
          ×
        </button>
      )}

      {open && (
        <div
          role="dialog"
          aria-label={label}
          className="absolute start-0 top-full z-30 mt-1 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => shift(-1)}
              aria-label={messages.prevMonth}
              className="h-9 w-9 rounded-lg text-lg text-slate-700 hover:bg-slate-100"
            >
              ›
            </button>
            <span className="text-sm font-semibold text-slate-900">
              {JALALI_MONTHS[view.jm - 1]} {toPersianDigits(view.jy)}
            </span>
            <button
              type="button"
              onClick={() => shift(1)}
              aria-label={messages.nextMonth}
              className="h-9 w-9 rounded-lg text-lg text-slate-700 hover:bg-slate-100"
            >
              ‹
            </button>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center text-xs text-slate-500">
            {WEEKDAYS.map((w) => (
              <span key={w} aria-hidden className="py-1">
                {w}
              </span>
            ))}
            {Array.from({ length: lead }, (_, i) => (
              <span key={`pad-${i}`} />
            ))}
            {Array.from({ length: days }, (_, i) => {
              const jd = i + 1;
              const isSel =
                selected?.jy === view.jy && selected?.jm === view.jm && selected?.jd === jd;
              const isToday = today.jy === view.jy && today.jm === view.jm && today.jd === jd;
              return (
                <button
                  key={jd}
                  type="button"
                  aria-pressed={isSel}
                  aria-label={`${toPersianDigits(jd)} ${JALALI_MONTHS[view.jm - 1]} ${toPersianDigits(view.jy)}`}
                  onClick={() => {
                    onChange(formatJalaliValue(view.jy, view.jm, jd));
                    setOpen(false);
                  }}
                  className={[
                    "h-9 rounded-lg text-sm",
                    isSel
                      ? "bg-slate-900 font-semibold text-white"
                      : isToday
                        ? "font-semibold text-slate-900 ring-1 ring-slate-400 hover:bg-slate-100"
                        : "text-slate-800 hover:bg-slate-100",
                  ].join(" ")}
                >
                  {toPersianDigits(jd)}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
