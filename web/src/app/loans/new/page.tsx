"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { type GridLender, ScheduleGrid, sumMilli } from "@/components/loan/ScheduleGrid";
import { NewPersonDialog } from "@/components/person/NewPersonDialog";
import { Card } from "@/components/ui/Card";
import {
  Button,
  Field,
  FormError,
  MoneyInput,
  Select,
  TextInput,
  Textarea,
} from "@/components/ui/form";
import { JalaliDatePicker, formatJalaliValue, parseJalali } from "@/components/ui/JalaliDatePicker";
import { type PickedPerson, PersonCombobox } from "@/components/ui/PersonCombobox";
import { PLATFORMS, platformLabel } from "@/components/ui/PlatformIcon";
import { ApiError, type Platform, api } from "@/lib/api/client";
import { fmtMoneyMT } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { todayJalali } from "@/lib/jalali";
import { useTopics, useWrite } from "@/lib/query/hooks";

type LenderRow = { key: number; person: PickedPerson | null; amount: string };
type Mode = "equal" | "custom";

/** Person picker with «عضو جدید» inline. */
function PersonPicker({
  value,
  onChange,
  invalid,
  id,
  describedBy,
}: {
  value: PickedPerson | null;
  onChange: (p: PickedPerson | null) => void;
  invalid?: boolean;
  id?: string;
  describedBy?: string;
}) {
  const [creating, setCreating] = useState<string | null>(null);
  return (
    <>
      <PersonCombobox
        id={id}
        value={value}
        onChange={onChange}
        invalid={invalid}
        describedBy={describedBy}
        onCreateNew={(name) => setCreating(name)}
      />
      {creating !== null && (
        <NewPersonDialog
          initialName={creating}
          onClose={() => setCreating(null)}
          onCreated={(p) => {
            onChange(p);
            setCreating(null);
          }}
        />
      )}
    </>
  );
}

export default function NewLoanPage() {
  const router = useRouter();
  const topics = useTopics();
  const today = todayJalali();
  const nextMonth = today.jm === 12 ? { y: today.jy + 1, m: 1 } : { y: today.jy, m: today.jm + 1 };

  const [borrower, setBorrower] = useState<PickedPerson | null>(null);
  const [topicId, setTopicId] = useState("");
  const [lenders, setLenders] = useState<LenderRow[]>([{ key: 1, person: null, amount: "" }]);
  const [months, setMonths] = useState("10");
  const [firstDue, setFirstDue] = useState(formatJalaliValue(nextMonth.y, nextMonth.m, 1));
  const [issued, setIssued] = useState(formatJalaliValue(today.jy, today.jm, today.jd));
  const [mode, setMode] = useState<Mode>("equal");
  const [schedule, setSchedule] = useState<GridLender[] | null>(null);
  const [guarantor, setGuarantor] = useState<PickedPerson | null>(null);
  const [liaison, setLiaison] = useState<PickedPerson | null>(null);
  const [platform, setPlatform] = useState<Platform | "">("");
  const [note, setNote] = useState("");
  const [flagged, setFlagged] = useState(false);

  const total = sumMilli(lenders.map((l) => l.amount)) / 1000;
  const lendersReady = lenders.every((l) => l.person && Number(l.amount) > 0);

  const preview = useWrite(() => {
    const fd = parseJalali(firstDue);
    return api.schedulePreview({
      lenders: lenders.map((l) => ({ person_id: l.person!.id, amount: l.amount })),
      months: Number(months),
      first_due: { year: fd!.jy, month: fd!.jm, day: fd!.jd },
    });
  });
  const create = useWrite(() => {
    const iss = parseJalali(issued);
    return api.createLoan({
      borrower_id: borrower!.id,
      topic_id: Number(topicId),
      lenders: (schedule ?? []).map((g) => ({
        person_id: Number(g.key),
        amount: g.amount,
        installments: g.installments.map((i) => ({
          year: i.year,
          month: i.month,
          day: i.day,
          amount: i.amount,
        })),
      })),
      issued: iss ? { year: iss.jy, month: iss.jm, day: iss.jd } : null,
      guarantor_id: guarantor?.id ?? null,
      liaison_person_id: liaison?.id ?? null,
      liaison_label: liaison?.full_name ?? null,
      source_platform: platform || null,
      description: note || null,
      note_flagged: flagged,
    });
  });
  const previewErr = preview.error instanceof ApiError ? preview.error : null;
  const err = create.error instanceof ApiError ? create.error : null;

  const buildSchedule = () =>
    preview.mutate(undefined, {
      onSuccess: (p) =>
        setSchedule(
          p.lenders.map((ln) => ({
            key: String(ln.person_id),
            name: lenders.find((l) => l.person?.id === ln.person_id)?.person?.full_name ?? "",
            amount: String(ln.amount),
            installments: ln.installments.map((i) => ({ ...i, amount: String(Number(i.amount)) })),
          })),
        ),
    });

  // Any change to who lends how much invalidates a generated schedule.
  const setLendersAndReset = (next: LenderRow[]) => {
    setLenders(next);
    setSchedule(null);
  };
  const scheduleOk =
    schedule !== null &&
    schedule.every(
      (g) =>
        sumMilli(g.installments.map((i) => i.amount)) === sumMilli([g.amount]) &&
        g.installments.length,
    );

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <Link href="/loans" className="text-sm text-slate-500 hover:text-slate-700">
          ← {messages.navLoans}
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.newLoan}</h1>
      </header>

      <Card className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={messages.borrower} required error={err?.fields.borrower_id}>
            {(a) => (
              <PersonPicker
                id={a.id}
                describedBy={a["aria-describedby"]}
                invalid={a["aria-invalid"]}
                value={borrower}
                onChange={setBorrower}
              />
            )}
          </Field>
          <Field label={messages.topic} required error={err?.fields.topic_id}>
            {(a) => (
              <Select {...a} value={topicId} onChange={(e) => setTopicId(e.target.value)}>
                <option value="">—</option>
                {topics.data?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-slate-700">
            {messages.loanLenders} <span className="text-overdue">*</span>
          </legend>
          {lenders.map((l, i) => (
            <div key={l.key} className="flex flex-wrap items-start gap-2">
              <div className="min-w-56 flex-1">
                <PersonPicker
                  value={l.person}
                  onChange={(p) =>
                    setLendersAndReset(lenders.map((x, j) => (j === i ? { ...x, person: p } : x)))
                  }
                  invalid={Boolean(err?.fields[`lenders.${i}`])}
                />
              </div>
              <div className="w-44">
                <MoneyInput
                  aria-label={messages.amount}
                  value={l.amount}
                  onChange={(v) =>
                    setLendersAndReset(lenders.map((x, j) => (j === i ? { ...x, amount: v } : x)))
                  }
                />
              </div>
              {lenders.length > 1 && (
                <Button
                  aria-label={messages.remove}
                  className="w-10 px-0"
                  onClick={() => setLendersAndReset(lenders.filter((_, j) => j !== i))}
                >
                  ×
                </Button>
              )}
            </div>
          ))}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button
              onClick={() =>
                setLendersAndReset([...lenders, { key: Date.now(), person: null, amount: "" }])
              }
            >
              + {messages.addLender}
            </Button>
            <span className="text-sm font-semibold text-slate-900">
              {messages.loanTotal}: {fmtMoneyMT(total)}
            </span>
          </div>
        </fieldset>
      </Card>

      <Card className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">{messages.scheduleTitle}</h2>
        <div
          role="radiogroup"
          aria-label={messages.scheduleMode}
          className="grid gap-2 md:grid-cols-2"
        >
          {(["equal", "custom"] as Mode[]).map((m) => (
            <label
              key={m}
              className={`flex cursor-pointer gap-3 rounded-xl border p-3 ${mode === m ? "border-slate-900 bg-slate-50" : "border-slate-200"}`}
            >
              <input type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} />
              <span>
                <span className="block text-sm font-semibold text-slate-900">
                  {m === "equal" ? messages.modeEqual : messages.modeCustom}
                </span>
                <span className="block text-xs text-slate-600">
                  {m === "equal" ? messages.modeEqualHint : messages.modeCustomHint}
                </span>
              </span>
            </label>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Field label={messages.months} error={previewErr?.fields.months}>
            {(a) => (
              <TextInput
                {...a}
                inputMode="numeric"
                dir="ltr"
                value={months}
                onChange={(e) => setMonths(e.target.value.replace(/[^\d]/g, "").slice(0, 2))}
                className="w-24 text-start"
              />
            )}
          </Field>
          <div className="space-y-1">
            <span className="block text-sm font-medium text-slate-700">{messages.firstDue}</span>
            <JalaliDatePicker label={messages.firstDue} value={firstDue} onChange={setFirstDue} />
          </div>
          <Button
            variant="primary"
            disabled={!lendersReady || !Number(months) || !firstDue || preview.isPending}
            onClick={buildSchedule}
          >
            {messages.buildSchedule}
          </Button>
        </div>
        <FormError
          message={previewErr && !previewErr.fields.months ? previewErr.message : undefined}
        />
        {schedule && (
          <ScheduleGrid
            lenders={schedule}
            editable={mode === "custom"}
            onChange={setSchedule}
            errors={err?.fields}
          />
        )}
      </Card>

      <Card className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={messages.guarantorLoan} error={err?.fields.guarantor_id}>
            {(a) => <PersonPicker id={a.id} value={guarantor} onChange={setGuarantor} />}
          </Field>
          <Field label={messages.liaison} error={err?.fields.liaison_person_id}>
            {(a) => <PersonPicker id={a.id} value={liaison} onChange={setLiaison} />}
          </Field>
          <Field label={messages.platform}>
            {(a) => (
              <Select
                {...a}
                value={platform}
                onChange={(e) => setPlatform(e.target.value as Platform)}
              >
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
        </div>
        <Field label={messages.paymentNote} error={err?.fields.description}>
          {(a) => <Textarea {...a} value={note} onChange={(e) => setNote(e.target.value)} />}
        </Field>
        <label className="inline-flex items-center gap-2 text-sm text-slate-800">
          <input type="checkbox" checked={flagged} onChange={(e) => setFlagged(e.target.checked)} />
          {messages.noteImportant}
        </label>
      </Card>

      <FormError
        message={
          err && !Object.keys(err.fields).some((k) => k.startsWith("lenders") || k.endsWith("_id"))
            ? err.message
            : undefined
        }
      />
      <div className="flex justify-end gap-2">
        <Link
          href="/loans"
          className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-slate-50"
        >
          {messages.cancel}
        </Link>
        <Button
          variant="primary"
          disabled={!borrower || !topicId || !scheduleOk || create.isPending}
          onClick={() =>
            create.mutate(undefined, { onSuccess: (r) => router.push(`/loans/${r.id}`) })
          }
        >
          {create.isPending ? messages.saving : messages.createLoan}
        </Button>
      </div>
    </section>
  );
}
