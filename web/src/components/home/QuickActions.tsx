"use client";

import Link from "next/link";
import { useState } from "react";

import { PaymentDialog } from "@/components/loan/PaymentDialog";
import { Button, Dialog, Field, FormError, TextInput, normalizeNumber } from "@/components/ui/form";
import { type LoanDetailResponse, api } from "@/lib/api/client";
import { messages } from "@/lib/i18n";

/** Home shortcuts: «ساخت سریع قرض» and «تسویه سریع قسط». */
export function QuickActions() {
  const [asking, setAsking] = useState(false);
  const [number, setNumber] = useState("");
  const [finding, setFinding] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [loan, setLoan] = useState<LoanDetailResponse | null>(null);

  const find = async () => {
    setFinding(true);
    setNotFound(false);
    try {
      const n = normalizeNumber(number);
      const hit = (await api.loans({ q: n, page_size: 20 })).items.find((l) => l.loan_number === n);
      if (!hit) {
        setNotFound(true);
        return;
      }
      setLoan(await api.loan(hit.id));
      setAsking(false);
    } finally {
      setFinding(false);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Link
        href="/loans/new"
        className="inline-flex h-11 items-center gap-2 rounded-lg bg-teal-700 px-5 text-sm font-semibold text-white hover:bg-teal-800"
      >
        <span aria-hidden className="text-lg leading-none">
          +
        </span>
        {messages.quickNewLoan}
      </Link>
      <Button className="h-11" onClick={() => setAsking(true)}>
        ✓ {messages.quickSettle}
      </Button>

      {asking && (
        <Dialog
          open
          onClose={() => setAsking(false)}
          title={messages.quickSettle}
          footer={
            <>
              <Button onClick={() => setAsking(false)}>{messages.cancel}</Button>
              <Button variant="primary" disabled={!number || finding} onClick={() => void find()}>
                {messages.findLoan}
              </Button>
            </>
          }
        >
          <Field label={messages.loanNumberToSettle} required>
            {(a) => (
              <TextInput
                {...a}
                autoFocus
                inputMode="numeric"
                dir="ltr"
                value={number}
                onChange={(e) => setNumber(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && number) void find();
                }}
                className="text-start"
              />
            )}
          </Field>
          <FormError message={notFound ? messages.loanNotFound : undefined} />
        </Dialog>
      )}
      {loan && <PaymentDialog loan={loan} initialMode="pick" onClose={() => setLoan(null)} />}
    </div>
  );
}
