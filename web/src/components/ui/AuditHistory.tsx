"use client";

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { platformLabel } from "@/components/ui/PlatformIcon";
import type { AuditEntry, Platform } from "@/lib/api/client";
import { fmtJalaliDate, fmtMoneyMT, toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useAudit } from "@/lib/query/hooks";

const ACTION_LABEL: Record<string, string> = {
  create: "ثبت",
  update: "ویرایش",
  void: "برگرداندن پرداخت",
  edit_schedule: "ویرایش جدول اقساط",
  link: "اتصال رابط",
  merge: "ادغام افراد تکراری",
  confirm_data_loss: "تأیید بارگذاری",
};
// Same action, but on a payment row shown in its loan's history.
const PAYMENT_ACTION_LABEL: Record<string, string> = {
  create: "ثبت پرداخت",
  void: "برگرداندن پرداخت",
};

const FIELD_LABEL: Record<string, string> = {
  topic_id: "موضوع",
  guarantor_id: "ضامن قرض",
  liaison_person_id: "رابط",
  liaison_label: "رابط (نام در اکسل)",
  source_platform: "پلتفرم",
  description: "یادداشت",
  note_flagged: "توضیح مهم",
  issued: "تاریخ پرداخت قرض",
  full_name: "نام",
  merged: "ادغام‌شده‌ها",
  phone: "شماره تماس",
  bank_account: "شماره حساب",
  messenger: "پیام‌رسان",
  contacts: "راه‌های ارتباطی",
  person_id: "فرد",
};

// Bookkeeping columns that change on every write and say nothing to a reader.
const NOISE = new Set(["id", "updated_at", "created_at", "import_id", "created_by", "phone_raw"]);

const money = (v: unknown) => fmtMoneyMT(Number(v));
const date = (y: unknown, m: unknown, d: unknown) =>
  y ? fmtJalaliDate(Number(y), Number(m), Number(d)) : "—";

/** Fold the stored y/m/d columns of the loan's issue date into one field. */
function withIssued(snap: Record<string, unknown>): Record<string, unknown> {
  if (!("issued_persian_year" in snap)) return snap;
  const { issued_persian_year: y, issued_persian_month: m, issued_persian_day: d, ...rest } = snap;
  return { ...rest, issued: y ? date(y, m, d) : null };
}

function show(e: AuditEntry, key: string, v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  const named = e.names?.[key]?.[String(v)];
  if (named) return named;
  if (typeof v === "boolean") return v ? "بله" : "خیر";
  if (key === "source_platform") return platformLabel(v as Platform);
  if (Array.isArray(v)) return `${toPersianDigits(v.length)} مورد`;
  if (typeof v === "object") return "…";
  return toPersianDigits(String(v));
}

/** Field-level "before → after" lines for one update. */
function changes(e: AuditEntry): { key: string; label: string; before: string; after: string }[] {
  const before = withIssued((e.before ?? {}) as Record<string, unknown>);
  const after = withIssued((e.after ?? {}) as Record<string, unknown>);
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  return [...keys]
    .filter((k) => !NOISE.has(k) && JSON.stringify(before[k]) !== JSON.stringify(after[k]))
    .map((k) => ({
      key: k,
      label: FIELD_LABEL[k] ?? k,
      before: show(e, k, before[k]),
      after: show(e, k, after[k]),
    }));
}

type Inst = {
  id: number;
  amount: string;
  due_persian_year: number;
  due_persian_month: number;
  due_day_of_month: number;
};

/** One line saying what an entry did when a field list would not help. */
function summary(e: AuditEntry): string | null {
  const a = (e.after ?? e.before ?? {}) as Record<string, unknown>;
  if (e.entity === "payment") {
    const credit = Number(a.credit ?? 0);
    return [
      money(a.amount),
      date(a.paid_persian_year, a.paid_persian_month, a.paid_persian_day),
      credit > 0 ? `${messages.creditHeld}: ${money(credit)}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (e.action === "edit_schedule") {
    const key = (i: Inst) =>
      `${i.amount}|${i.due_persian_year}/${i.due_persian_month}/${i.due_day_of_month}`;
    const old = new Map(((e.before?.installments ?? []) as Inst[]).map((i) => [i.id, key(i)]));
    const now = (e.after?.installments ?? []) as Inst[];
    const changed =
      now.filter((i) => old.get(i.id) !== key(i)).length +
      [...old.keys()].filter((id) => !now.some((i) => i.id === id)).length;
    return messages.installmentsChanged.replace("{n}", toPersianDigits(changed));
  }
  if (e.action === "create" && e.entity === "loan") return money(a.total_amount);
  return null;
}

const fmtTime = (iso: string) =>
  new Intl.DateTimeFormat("fa-IR-u-ca-persian", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );

/** «تاریخچه تغییرات»: who changed what, when, with before → after per field. */
export function AuditHistory({ entity, id }: { entity: "loan" | "person"; id: number }) {
  const [open, setOpen] = useState(false);
  const log = useAudit(entity, open ? id : null);
  return (
    <Card className="p-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-start text-lg font-semibold text-slate-900"
      >
        {messages.historyTitle}
        <span aria-hidden className="text-sm text-slate-500">
          {open ? "▲" : "▼"}
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-100">
          {log.data && log.data.length === 0 && (
            <p className="px-4 py-3 text-sm text-slate-500">{messages.historyEmpty}</p>
          )}
          <ol className="divide-y divide-slate-100">
            {log.data?.map((e) => {
              const diff = changes(e);
              const sum = summary(e);
              return (
                <li key={e.id} className="space-y-1 px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-semibold text-slate-900">
                      {(e.entity === "payment" ? PAYMENT_ACTION_LABEL[e.action] : null) ??
                        ACTION_LABEL[e.action] ??
                        e.action}
                    </span>
                    <span className="text-xs text-slate-500">
                      {e.username} · {fmtTime(e.at)}
                    </span>
                  </div>
                  {sum && <p className="text-xs text-slate-700">{sum}</p>}
                  {e.action === "update" && diff.length > 0 && (
                    <dl className="space-y-0.5 text-xs text-slate-700">
                      {diff.map((d) => (
                        <div key={d.key} className="flex flex-wrap gap-x-1.5">
                          <dt className="text-slate-500">{d.label}:</dt>
                          <dd>
                            <del className="text-slate-500 decoration-red-400">{d.before}</del>
                            <span aria-hidden> ← </span>
                            <span className="sr-only"> به </span>
                            <ins className="font-medium no-underline">{d.after}</ins>
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </Card>
  );
}
