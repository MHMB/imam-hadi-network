"use client";

import { useState } from "react";

import { Card } from "@/components/ui/Card";
import type { AuditEntry } from "@/lib/api/client";
import { toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useAudit } from "@/lib/query/hooks";

const ACTION_LABEL: Record<string, string> = {
  create: "ثبت",
  update: "ویرایش",
  void: "برگرداندن پرداخت",
  edit_schedule: "ویرایش جدول اقساط",
  link: "اتصال رابط",
  confirm_data_loss: "تأیید بارگذاری",
};

// Bookkeeping columns that change on every write and say nothing to a reader.
const NOISE = new Set(["id", "updated_at", "created_at", "import_id", "created_by"]);

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "بله" : "خیر";
  if (typeof v === "object") return toPersianDigits(JSON.stringify(v).length) + " مورد";
  return toPersianDigits(String(v));
}

/** Field-level "before → after" lines for one audit entry. */
function changes(e: AuditEntry): { key: string; before: string; after: string }[] {
  const before = (e.before ?? {}) as Record<string, unknown>;
  const after = (e.after ?? {}) as Record<string, unknown>;
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  return [...keys]
    .filter((k) => !NOISE.has(k) && JSON.stringify(before[k]) !== JSON.stringify(after[k]))
    .map((k) => ({ key: k, before: show(before[k]), after: show(after[k]) }));
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
              return (
                <li key={e.id} className="space-y-1 px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-semibold text-slate-900">
                      {ACTION_LABEL[e.action] ?? e.action}
                    </span>
                    <span className="text-xs text-slate-500">
                      {e.username} · {fmtTime(e.at)}
                    </span>
                  </div>
                  {e.action === "update" && diff.length > 0 && (
                    <ul className="space-y-0.5 text-xs text-slate-700">
                      {diff.map((d) => (
                        <li key={d.key}>
                          <span className="text-slate-500">{d.key}:</span>{" "}
                          <span className="line-through decoration-red-400">{d.before}</span> ←{" "}
                          <span className="font-medium">{d.after}</span>
                        </li>
                      ))}
                    </ul>
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
