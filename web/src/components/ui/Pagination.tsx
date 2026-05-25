"use client";

import { toPersianDigits } from "@/lib/format";

export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  const prev = () => onChange(Math.max(1, page - 1));
  const next = () => onChange(Math.min(pages, page + 1));

  return (
    <nav
      aria-label="صفحه‌بندی"
      className="flex items-center justify-between gap-3 px-2 py-3 text-sm text-slate-600"
    >
      <button
        type="button"
        onClick={prev}
        disabled={page <= 1}
        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        قبلی
      </button>
      <span>
        صفحه {toPersianDigits(page)} از {toPersianDigits(pages)} ({toPersianDigits(total)} مورد)
      </span>
      <button
        type="button"
        onClick={next}
        disabled={page >= pages}
        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        بعدی
      </button>
    </nav>
  );
}
