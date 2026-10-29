"use client";

import { useState } from "react";

import { type GridLender, ScheduleGrid, sumMilli } from "@/components/loan/ScheduleGrid";
import { Button, Dialog, Field, FormError, Select, Textarea } from "@/components/ui/form";
import { JalaliDatePicker, formatJalaliValue, parseJalali } from "@/components/ui/JalaliDatePicker";
import { type PickedPerson, PersonCombobox } from "@/components/ui/PersonCombobox";
import { PLATFORMS, platformLabel } from "@/components/ui/PlatformIcon";
import { ApiError, type LoanDetailResponse, type Platform, api } from "@/lib/api/client";
import { fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { usePayments, useTopics, useWrite } from "@/lib/query/hooks";

type LoanFields = {
  id: number;
  topic_id?: number;
  description: string | null;
  note_flagged: boolean;
  source_platform: Platform | null;
  issued: [number, number, number] | null;
  liaison_person: { id: number; full_name: string } | null;
};

export const loanFields = (d: LoanDetailResponse) => d.loan as unknown as LoanFields;

/** Loan details: topic, guarantor, liaison, platform, issue date, note + flag. */
export function EditLoanDialog({
  detail,
  onClose,
}: {
  detail: LoanDetailResponse;
  onClose: () => void;
}) {
  const f = loanFields(detail);
  const topics = useTopics();
  const [topicId, setTopicId] = useState(String(detail.topic.id));
  const [guarantor, setGuarantor] = useState<PickedPerson | null>(detail.guarantor ?? null);
  const [liaison, setLiaison] = useState<PickedPerson | null>(f.liaison_person);
  const [platform, setPlatform] = useState<Platform | "">(f.source_platform ?? "");
  const [issued, setIssued] = useState(f.issued ? formatJalaliValue(...f.issued) : "");
  const [note, setNote] = useState(f.description ?? "");
  const [flagged, setFlagged] = useState(f.note_flagged);
  const save = useWrite(() => {
    const d = parseJalali(issued);
    return api.updateLoan(f.id, {
      topic_id: Number(topicId),
      guarantor_id: guarantor?.id ?? null,
      liaison_person_id: liaison?.id ?? null,
      source_platform: platform || null,
      issued: d ? { year: d.jy, month: d.jm, day: d.jd } : null,
      description: note || null,
      note_flagged: flagged,
    });
  });
  const err = save.error instanceof ApiError ? save.error : null;
  return (
    <Dialog
      open
      onClose={onClose}
      title={messages.editLoan}
      footer={
        <>
          <Button onClick={onClose}>{messages.cancel}</Button>
          <Button
            variant="primary"
            disabled={save.isPending}
            onClick={() => save.mutate(undefined, { onSuccess: onClose })}
          >
            {save.isPending ? messages.saving : messages.save}
          </Button>
        </>
      }
    >
      <Field label={messages.topic} error={err?.fields.topic_id}>
        {(a) => (
          <Select {...a} value={topicId} onChange={(e) => setTopicId(e.target.value)}>
            {topics.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label={messages.guarantorLoan} error={err?.fields.guarantor_id}>
        {(a) => <PersonCombobox id={a.id} value={guarantor} onChange={setGuarantor} />}
      </Field>
      <Field label={messages.liaison} error={err?.fields.liaison_person_id}>
        {(a) => <PersonCombobox id={a.id} value={liaison} onChange={setLiaison} />}
      </Field>
      <Field label={messages.platform}>
        {(a) => (
          <Select {...a} value={platform} onChange={(e) => setPlatform(e.target.value as Platform)}>
            <option value="">—</option>
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {platformLabel(p)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <div className="space-y-1">
        <span className="block text-sm font-medium text-slate-700">{messages.issuedDate}</span>
        <JalaliDatePicker label={messages.issuedDate} value={issued} onChange={setIssued} />
      </div>
      <Field label={messages.paymentNote}>
        {(a) => <Textarea {...a} value={note} onChange={(e) => setNote(e.target.value)} />}
      </Field>
      <label className="inline-flex items-center gap-2 text-sm text-slate-800">
        <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} />
        {messages.noteImportant}
      </label>
      <FormError message={err && Object.keys(err.fields).length === 0 ? err.message : undefined} />
    </Dialog>
  );
}

/** Edit the schedule; money already paid stays (paid rows can't be removed or cut below it). */
export function EditScheduleDialog({
  detail,
  onClose,
}: {
  detail: LoanDetailResponse;
  onClose: () => void;
}) {
  const f = loanFields(detail);
  const [grid, setGrid] = useState<GridLender[]>(() =>
    detail.lenders.map((ln) => ({
      key: String(ln.party_id),
      name: ln.person.full_name,
      amount: String(Number(ln.amount)),
      installments: ln.installments.map((i) => ({
        id: i.id,
        year: i.due_persian_year,
        month: i.due_persian_month,
        day: i.due_day_of_month,
        amount: String(Number(i.amount)),
        paid: String(Number(i.amount_paid)),
      })),
    })),
  );
  const save = useWrite(() =>
    api.editSchedule(f.id, {
      lenders: grid.map((g) => ({
        party_id: Number(g.key),
        installments: g.installments.map((i) => ({
          id: i.id ?? null,
          year: i.year,
          month: i.month,
          day: i.day,
          amount: i.amount,
        })),
      })),
    }),
  );
  const err = save.error instanceof ApiError ? save.error : null;
  const ok = grid.every(
    (g) =>
      g.installments.length > 0 &&
      sumMilli(g.installments.map((i) => i.amount)) === sumMilli([g.amount]),
  );
  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={messages.editSchedule}
      footer={
        <>
          <Button onClick={onClose}>{messages.cancel}</Button>
          <Button
            variant="primary"
            disabled={!ok || save.isPending}
            onClick={() => save.mutate(undefined, { onSuccess: onClose })}
          >
            {save.isPending ? messages.saving : messages.save}
          </Button>
        </>
      }
    >
      <ScheduleGrid lenders={grid} editable onChange={setGrid} errors={err?.fields} />
      <FormError
        message={
          err && !Object.keys(err.fields).some((k) => k.startsWith("lenders"))
            ? err.message
            : undefined
        }
      />
    </Dialog>
  );
}

/** Payments on the loan, newest first, each with its split and an undo. */
export function PaymentsList({ loanId }: { loanId: number }) {
  const payments = usePayments(loanId);
  const voidIt = useWrite((id: number) => api.voidPayment(id));
  if (!payments.data || payments.data.length === 0) return null;
  return (
    <section
      aria-labelledby="payments-h"
      className="rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <h2
        id="payments-h"
        className="border-b border-slate-100 px-4 py-3 text-lg font-semibold text-slate-900"
      >
        {messages.paymentsTitle} ({toPersianDigits(payments.data.length)})
      </h2>
      <ul className="divide-y divide-slate-100">
        {payments.data.map((p) => {
          const voided = p.voided_at !== null;
          return (
            <li key={p.id} className={`space-y-1 px-4 py-3 text-sm ${voided ? "opacity-60" : ""}`}>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className={`font-semibold text-slate-900 ${voided ? "line-through" : ""}`}>
                  {fmtMoneyMT(Number(p.amount))}
                </span>
                <span className="text-slate-600">{fmtJalaliDate(...p.paid)}</span>
                {Number(p.credit) > 0 && (
                  <span className="rounded bg-amber-100 px-2 text-xs text-amber-900">
                    {messages.creditHeld}: {fmtMoneyMT(Number(p.credit))}
                  </span>
                )}
                <span className="text-xs text-slate-500">
                  {messages.createdBy}: {p.created_by}
                </span>
                <span className="ms-auto">
                  {voided ? (
                    <span className="text-xs text-slate-500">{messages.paymentVoided}</span>
                  ) : (
                    <Button
                      variant="danger"
                      className="h-8 px-3 text-xs"
                      disabled={voidIt.isPending}
                      onClick={() => {
                        if (window.confirm(messages.paymentVoidConfirm)) voidIt.mutate(p.id);
                      }}
                    >
                      {messages.paymentVoid}
                    </Button>
                  )}
                </span>
              </div>
              {p.note && <p className="text-xs text-slate-600">{p.note}</p>}
              <ul className="flex flex-wrap gap-2 text-xs text-slate-600">
                {p.allocations.map((a) => (
                  <li key={a.installment_id} className="rounded bg-slate-100 px-2 py-0.5">
                    {a.lender_name} · {fmtJalaliDate(...a.due)} · {fmtMoneyMT(Number(a.amount))}
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
