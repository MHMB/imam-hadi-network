"use client";

import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  useEffect,
  useId,
  useRef,
} from "react";

import { messages } from "@/lib/i18n";

/** Shared form primitives: label above, error below, wired with aria-describedby. */

const CONTROL =
  "w-full rounded-lg border bg-white px-3 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900/20 disabled:bg-slate-50";

export function Field({
  label,
  error,
  hint,
  required,
  children,
}: {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: (props: {
    id: string;
    "aria-describedby"?: string;
    "aria-invalid"?: boolean;
  }) => ReactNode;
}) {
  const id = useId();
  const described = error ? `${id}-err` : hint ? `${id}-hint` : undefined;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="ms-0.5 text-overdue">*</span>}
      </label>
      {children({ id, "aria-describedby": described, "aria-invalid": error ? true : undefined })}
      {error ? (
        <p id={`${id}-err`} className="text-xs text-overdue" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function TextInput({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`${CONTROL} h-10 ${props["aria-invalid"] ? "border-overdue" : "border-slate-300"} ${className}`}
    />
  );
}

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** Persian/Arabic digits and the Persian decimal mark → a plain `123.45` string. */
export function normalizeNumber(raw: string): string {
  return raw
    .replace(/[۰-۹]/g, (d) => String(PERSIAN_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(ARABIC_DIGITS.indexOf(d)))
    .replace(/[٫,]/g, ".")
    .replace(/[^\d.]/g, "");
}

/** Million-toman amount: accepts Persian digits, keeps up to 3 decimals. */
export function MoneyInput({
  value,
  onChange,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative">
      <TextInput
        {...props}
        inputMode="decimal"
        dir="ltr"
        value={value}
        onChange={(e) => {
          const v = normalizeNumber(e.target.value);
          if (/^\d*(\.\d{0,3})?$/.test(v)) onChange(v);
        }}
        className="pe-14 text-start"
      />
      <span className="pointer-events-none absolute end-3 top-2.5 text-xs text-slate-500">
        {messages.flowMillionShort}
      </span>
    </div>
  );
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`${CONTROL} h-10 cursor-pointer ${props["aria-invalid"] ? "border-overdue" : "border-slate-300"} ${className}`}
    />
  );
}

export function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`${CONTROL} min-h-20 py-2 ${props["aria-invalid"] ? "border-overdue" : "border-slate-300"} ${className}`}
    />
  );
}

export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const look = {
    primary: "border-transparent bg-teal-700 text-white hover:bg-teal-800",
    secondary: "border-slate-300 bg-white text-slate-900 hover:bg-slate-50",
    danger: "border-red-300 bg-white text-red-700 hover:bg-red-50",
  }[variant];
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${look} ${className}`}
    />
  );
}

/** Modal on native <dialog>: focus trap, Escape and backdrop come from the browser. */
export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      // showModal focuses the first focusable (the close button); start on the first field instead.
      d.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea")?.focus();
    }
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      className={`w-[calc(100%-2rem)] rounded-2xl border border-slate-200 p-0 shadow-xl backdrop:bg-slate-900/40 ${wide ? "max-w-4xl" : "max-w-lg"}`}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <h2 className="text-lg font-bold text-slate-900">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              aria-label={messages.close}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xl text-slate-500 hover:bg-slate-100"
            >
              ×
            </button>
          </div>
          <div className="space-y-4 overflow-y-auto px-5 py-4">{children}</div>
          {footer && (
            <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-5 py-3">
              {footer}
            </div>
          )}
        </div>
      )}
    </dialog>
  );
}

/** Form-level error line (non-field errors, network failures). */
export function FormError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p
      className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
      role="alert"
    >
      {message}
    </p>
  );
}
