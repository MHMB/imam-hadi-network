"use client";

import { Button, MoneyInput } from "@/components/ui/form";
import { JalaliDatePicker, formatJalaliValue, parseJalali } from "@/components/ui/JalaliDatePicker";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";

export type GridInstallment = {
  id?: number | null;
  year: number;
  month: number;
  day: number;
  amount: string;
  /** Already paid on this installment (schedule edit): amount can't go below it. */
  paid?: string;
};
export type GridLender = {
  key: string;
  name: string;
  amount: string;
  installments: GridInstallment[];
};

/** Exact sum of decimal strings in thousandths (avoids float drift on money). */
export const sumMilli = (xs: string[]) =>
  xs.reduce((acc, x) => acc + Math.round(Number(x || 0) * 1000), 0);

const nextMonth = (i: GridInstallment): GridInstallment => {
  const m = i.month === 12 ? 1 : i.month + 1;
  return {
    year: i.month === 12 ? i.year + 1 : i.year,
    month: m,
    day: Math.min(i.day, 29),
    amount: "",
  };
};

/**
 * One block per lender: their installments (date + amount) and a live check
 * that the rows add up to the lender's amount.  Read-only unless `editable`.
 */
export function ScheduleGrid({
  lenders,
  editable,
  onChange,
  errors = {},
}: {
  lenders: GridLender[];
  editable: boolean;
  onChange?: (next: GridLender[]) => void;
  errors?: Record<string, string>;
}) {
  const update = (li: number, rows: GridInstallment[]) =>
    onChange?.(lenders.map((l, j) => (j === li ? { ...l, installments: rows } : l)));

  return (
    <div className="space-y-4">
      {lenders.map((ln, li) => {
        const diff = sumMilli(ln.installments.map((i) => i.amount)) - sumMilli([ln.amount]);
        const error = errors[`lenders.${li}`];
        return (
          <section key={ln.key} className="rounded-xl border border-slate-200">
            <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2">
              <h3 className="text-sm font-semibold text-slate-900">{ln.name}</h3>
              <span className="text-xs text-slate-600">
                {fmtMoneyMT(Number(ln.amount || 0))} · {messages.rowSum}:{" "}
                {fmtMoneyMT(sumMilli(ln.installments.map((i) => i.amount)) / 1000)}{" "}
                {diff === 0 ? (
                  <span className="font-semibold text-paid">✓ {messages.rowOk}</span>
                ) : (
                  <span className="font-semibold text-overdue">{messages.rowMismatch}</span>
                )}
              </span>
            </header>
            <ol className="divide-y divide-slate-100">
              {ln.installments.map((inst, ii) => (
                <li key={ii} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="w-6 text-slate-400">{toPersianDigits(ii + 1)}</span>
                  {editable ? (
                    <>
                      <JalaliDatePicker
                        label={messages.dueDate}
                        value={formatJalaliValue(inst.year, inst.month, inst.day)}
                        onChange={(v) => {
                          const d = parseJalali(v);
                          if (!d) return;
                          update(
                            li,
                            ln.installments.map((x, k) =>
                              k === ii ? { ...x, year: d.jy, month: d.jm, day: d.jd } : x,
                            ),
                          );
                        }}
                      />
                      <div className="w-40">
                        <MoneyInput
                          aria-label={messages.amount}
                          value={inst.amount}
                          onChange={(v) =>
                            update(
                              li,
                              ln.installments.map((x, k) => (k === ii ? { ...x, amount: v } : x)),
                            )
                          }
                        />
                      </div>
                      {inst.paid && Number(inst.paid) > 0 ? (
                        <span className="text-xs text-paid">
                          {messages.paidPart}: {fmtMoneyMT(Number(inst.paid))}
                        </span>
                      ) : (
                        <Button
                          aria-label={messages.remove}
                          className="w-10 px-0"
                          onClick={() =>
                            update(
                              li,
                              ln.installments.filter((_, k) => k !== ii),
                            )
                          }
                        >
                          ×
                        </Button>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="w-40 text-slate-700">
                        {toPersianDigits(inst.day)} {JALALI_MONTHS[inst.month - 1]}{" "}
                        {toPersianDigits(inst.year)}
                      </span>
                      <span className="font-medium text-slate-900">
                        {fmtMoneyMT(Number(inst.amount))}
                      </span>
                    </>
                  )}
                </li>
              ))}
            </ol>
            {editable && (
              <div className="border-t border-slate-100 px-3 py-2">
                <Button
                  onClick={() => {
                    const last = ln.installments[ln.installments.length - 1];
                    const fresh: GridInstallment = last
                      ? nextMonth(last)
                      : { year: 1405, month: 1, day: 1, amount: "" };
                    update(li, [...ln.installments, fresh]);
                  }}
                >
                  + {messages.addInstallment}
                </Button>
              </div>
            )}
            {error && (
              <p
                className="border-t border-red-100 bg-red-50 px-3 py-2 text-xs text-red-800"
                role="alert"
              >
                {error}
              </p>
            )}
          </section>
        );
      })}
    </div>
  );
}
