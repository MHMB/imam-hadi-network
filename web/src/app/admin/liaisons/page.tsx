"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Button, FormError } from "@/components/ui/form";
import { PersonCombobox } from "@/components/ui/PersonCombobox";
import { EmptyState, ErrorState, Loading } from "@/components/ui/States";
import { ApiError, api } from "@/lib/api/client";
import { toPersianDigits } from "@/lib/format";
import { messages } from "@/lib/i18n";
import { useLiaisons, useWrite } from "@/lib/query/hooks";

/** Link every رابط label from the sheet to a person (or mark it a channel). */
export default function LiaisonsPage() {
  const rows = useLiaisons();
  const link = useWrite((body: { label: string; person_id: number | null }) =>
    api.linkLiaison(body),
  );
  const [editing, setEditing] = useState<string | null>(null);

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <Link href="/admin" className="text-sm text-slate-500 hover:text-slate-700">
          ← {messages.navAdmin}
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 md:text-3xl">{messages.liaisonsTitle}</h1>
        <p className="max-w-3xl text-sm text-slate-600">{messages.liaisonsHint}</p>
      </header>
      {rows.isLoading && <Loading />}
      {rows.isError && <ErrorState />}
      {rows.data && rows.data.length === 0 && <EmptyState />}
      <FormError message={link.error instanceof ApiError ? link.error.message : undefined} />
      {rows.data && rows.data.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-2 text-start font-medium">{messages.liaisonLabel}</th>
                <th className="px-4 py-2 text-start font-medium">{messages.kpiLoanCount}</th>
                <th className="px-4 py-2 text-start font-medium">{messages.liaisonPerson}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.data.map((r) => (
                <tr key={r.label}>
                  <td className="px-4 py-3 font-medium text-slate-900">{r.label}</td>
                  <td className="px-4 py-3">{toPersianDigits(r.loan_count)}</td>
                  <td className="min-w-64 px-4 py-3">
                    {editing === r.label ? (
                      <PersonCombobox
                        value={null}
                        onChange={(p) => {
                          if (p) link.mutate({ label: r.label, person_id: p.id });
                          setEditing(null);
                        }}
                      />
                    ) : r.person ? (
                      <span className="inline-flex items-center gap-2">
                        <Link href={`/persons/${r.person.id}`} className="hover:underline">
                          {r.person.full_name}
                        </Link>
                        {r.confirmed && <Badge tone="paid">{messages.liaisonConfirmed}</Badge>}
                      </span>
                    ) : r.confirmed ? (
                      <span className="text-slate-500">{messages.liaisonIsChannel}</span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-end">
                    <div className="inline-flex gap-2">
                      <Button
                        disabled={link.isPending}
                        onClick={() => setEditing(editing === r.label ? null : r.label)}
                      >
                        {messages.edit}
                      </Button>
                      <Button
                        disabled={link.isPending}
                        onClick={() => link.mutate({ label: r.label, person_id: null })}
                      >
                        {messages.liaisonIsChannel}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </section>
  );
}
