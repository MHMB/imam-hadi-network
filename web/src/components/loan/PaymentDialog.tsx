"use client";

import { useEffect, useMemo, useState } from "react";

import { Button, Dialog, Field, FormError, MoneyInput, TextInput } from "@/components/ui/form";
import { JalaliDatePicker, formatJalaliValue, parseJalali } from "@/components/ui/JalaliDatePicker";
import { ApiError, type LoanDetailResponse, type PaymentPreview, api } from "@/lib/api/client";
import { fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { JALALI_MONTHS, messages } from "@/lib/i18n";
import { todayJalali } from "@/lib/jalali";
import { useWrite } from "@/lib/query/hooks";

export type PayMode = "schedule" | "pick" | "manual";

type OpenInst = {
  id: number;
  lender: string;
  y: number;
  m: number;
  d: number;
  remaining: number; // thousandths of a million toman
};

const milli = (v: string | number) => Math.round(Number(v || 0) * 1000);
const fromMilli = (n: number) => (n / 1000).toFixed(3).replace(/\.?0+$/, "");
const dateLabel = (y: number, m: number, d: number) =>
  `${toPersianDigits(d)} ${JALALI_MONTHS[m - 1]} ${toPersianDigits(y)}`;

/** Open installments in schedule order (oldest due, then lender order). */
function openInstallments(loan: LoanDetailResponse): OpenInst[] {
  return loan.lenders
    .flatMap((ln, order) =>
      ln.installments
        .filter((i) => milli(i.amount) > milli(i.amount_paid))
        .map((i) => ({
          id: i.id,
          lender: ln.person.full_name,
          y: i.due_persian_year,
          m: i.due_persian_month,
          d: i.due_day_of_month,
          remaining: milli(i.amount) - milli(i.amount_paid),
          order,
        })),
    )
    .sort((a, b) => a.y - b.y || a.m - b.m || a.d - b.d || a.order - b.order);
}

/**
 * Record a payment.  «طبق جدول اقساط»: the server splits it oldest-due-first
 * (shown before saving).  «انتخاب اقساط»: tick whole installments.  «تقسیم
 * دستی»: type each installment's share.  Anything left over is the
 * borrower's credit and must be confirmed.
 */
export function PaymentDialog({
  loan,
  initialMode = "schedule",
  onClose,
}: {
  loan: LoanDetailResponse;
  initialMode?: PayMode;
  onClose: () => void;
}) {
  const loanId = Number((loan.loan as Record<string, unknown>).id);
  const open = useMemo(() => openInstallments(loan), [loan]);
  const t = todayJalali();
  const [mode, setMode] = useState<PayMode>(initialMode);
  const [amount, setAmount] = useState("");
  const [paid, setPaid] = useState(formatJalaliValue(t.jy, t.jm, t.jd));
  const [note, setNote] = useState("");
  const [picked, setPicked] = useState<Set<number>>(() =>
    initialMode === "pick" && open[0] ? new Set([open[0].id]) : new Set(),
  );
  const [manual, setManual] = useState<Record<number, string>>({});
  const [confirmCredit, setConfirmCredit] = useState(false);
  const [preview, setPreview] = useState<PaymentPreview | null>(null);

  // Ticking installments decides the amount.
  const pickedSum = open.filter((o) => picked.has(o.id)).reduce((a, o) => a + o.remaining, 0);
  const effectiveAmount = mode === "pick" ? fromMilli(pickedSum) : amount;

  useEffect(() => {
    setPreview(null);
    if (mode !== "schedule" || !(Number(amount) > 0)) return;
    let current = true; // ignore a late answer for an amount already changed
    const h = setTimeout(() => {
      api.paymentPreview(loanId, amount).then(
        (p) => current && setPreview(p),
        () => current && setPreview(null),
      );
    }, 300);
    return () => {
      current = false;
      clearTimeout(h);
    };
  }, [mode, amount, loanId]);

  // A credit confirmation is for one exact amount and split: any change asks again.
  useEffect(() => {
    setConfirmCredit(false);
  }, [mode, amount, picked, manual]);

  const allocations =
    mode === "pick"
      ? open
          .filter((o) => picked.has(o.id))
          .map((o) => ({ installment_id: o.id, amount: fromMilli(o.remaining) }))
      : mode === "manual"
        ? Object.entries(manual)
            .filter(([, v]) => Number(v) > 0)
            .map(([id, v]) => ({ installment_id: Number(id), amount: v }))
        : null;
  const allocatedMilli =
    allocations?.reduce((a, x) => a + milli(x.amount), 0) ??
    (preview ? milli(effectiveAmount) - milli(preview.credit) : 0);
  const creditMilli = milli(effectiveAmount) - allocatedMilli;

  const save = useWrite(() => {
    const d = parseJalali(paid)!;
    return api.createPayment(loanId, {
      amount: effectiveAmount,
      paid: { year: d.jy, month: d.jm, day: d.jd },
      note: note || null,
      allocations,
      confirm_credit: confirmCredit,
    });
  });
  const err = save.error instanceof ApiError ? save.error : null;
  const canSave =
    milli(effectiveAmount) > 0 &&
    parseJalali(paid) !== null &&
    (creditMilli <= 0 || confirmCredit) &&
    creditMilli >= 0 &&
    !save.isPending;

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={`${messages.recordPayment} · ${messages.loanNumber} ${toPersianDigits(String((loan.loan as Record<string, unknown>).loan_number))}`}
      footer={
        <>
          <Button onClick={onClose}>{messages.cancel}</Button>
          <Button
            variant="primary"
            disabled={!canSave}
            onClick={() => save.mutate(undefined, { onSuccess: onClose })}
          >
            {save.isPending ? messages.saving : messages.recordPayment}
          </Button>
        </>
      }
    >
      <div role="radiogroup" aria-label={messages.recordPayment} className="flex flex-wrap gap-2">
        {(
          [
            ["schedule", messages.splitBySchedule],
            ["pick", messages.splitPick],
            ["manual", messages.splitManual],
          ] as [PayMode, string][]
        ).map(([m, label]) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={mode === m}
            onClick={() => setMode(m)}
            className={`h-9 rounded-full border px-4 text-sm font-medium ${mode === m ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-800"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {mode === "pick" ? (
          <div className="space-y-1">
            <span className="block text-sm font-medium text-slate-700">
              {messages.paymentAmount}
            </span>
            <p className="flex h-10 items-center rounded-lg bg-slate-50 px-3 text-sm font-semibold">
              {fmtMoneyMT(pickedSum / 1000)}
            </p>
          </div>
        ) : (
          <Field label={messages.paymentAmount} required error={err?.fields.amount}>
            {(a) => <MoneyInput {...a} value={amount} onChange={setAmount} />}
          </Field>
        )}
        <div className="space-y-1">
          <span className="block text-sm font-medium text-slate-700">{messages.paymentDate}</span>
          <JalaliDatePicker label={messages.paymentDate} value={paid} onChange={setPaid} />
        </div>
      </div>

      <section
        aria-label={messages.openInstallments}
        className="rounded-xl border border-slate-200"
      >
        <h3 className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-900">
          {messages.openInstallments}
        </h3>
        <ul className="max-h-72 divide-y divide-slate-100 overflow-y-auto">
          {open.map((o) => {
            const scheduled = preview?.allocations.find((a) => a.installment_id === o.id);
            return (
              <li key={o.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                {mode === "pick" && (
                  <input
                    type="checkbox"
                    aria-label={`${o.lender} ${dateLabel(o.y, o.m, o.d)}`}
                    checked={picked.has(o.id)}
                    onChange={(e) =>
                      setPicked((s) => {
                        const n = new Set(s);
                        if (e.target.checked) n.add(o.id);
                        else n.delete(o.id);
                        return n;
                      })
                    }
                  />
                )}
                <span className="w-36 text-slate-700">{dateLabel(o.y, o.m, o.d)}</span>
                <span className="min-w-28 flex-1 text-slate-900">{o.lender}</span>
                <span className="text-xs text-slate-500">
                  {messages.remaining}: {fmtMoneyMT(o.remaining / 1000)}
                </span>
                {mode === "manual" && (
                  <div className="w-36">
                    <MoneyInput
                      aria-label={`${messages.allocation} ${o.lender}`}
                      value={manual[o.id] ?? ""}
                      onChange={(v) => setManual((s) => ({ ...s, [o.id]: v }))}
                    />
                  </div>
                )}
                {mode === "schedule" && scheduled && (
                  <span className="rounded-full bg-paid/10 px-2 py-0.5 text-xs font-semibold text-paid">
                    + {fmtMoneyMT(Number(scheduled.amount))}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {creditMilli > 0 && (
        <div
          className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950"
          role="alert"
        >
          <p>
            {messages.creditWarning.replace("{amount}", toPersianDigits(fromMilli(creditMilli)))}
          </p>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={confirmCredit}
              onChange={(e) => setConfirmCredit(e.target.checked)}
              className="mt-1"
            />
            {messages.creditConfirm}
          </label>
        </div>
      )}
      {creditMilli < 0 && (
        <p className="text-sm text-overdue" role="alert">
          {err?.fields.allocations ?? messages.rowMismatch}
        </p>
      )}

      <Field label={messages.paymentNote}>
        {(a) => <TextInput {...a} value={note} onChange={(e) => setNote(e.target.value)} />}
      </Field>
      <FormError
        message={err && !err.fields.amount ? (err.fields.allocations ?? err.message) : undefined}
      />
    </Dialog>
  );
}
