"use client";

import { useEffect, useId, useState } from "react";

import { messages } from "@/lib/i18n";
import { usePersons } from "@/lib/query/hooks";

export type PickedPerson = { id: number; full_name: string };

/**
 * Search-as-you-type person picker (name or phone).  Shows the choice as a
 * removable chip; offers «عضو جدید» when nothing matches.
 */
export function PersonCombobox({
  value,
  onChange,
  onCreateNew,
  placeholder,
  invalid,
  describedBy,
  id,
}: {
  value: PickedPerson | null;
  onChange: (p: PickedPerson | null) => void;
  onCreateNew?: (typedName: string) => void;
  placeholder?: string;
  invalid?: boolean;
  describedBy?: string;
  id?: string;
}) {
  const listId = useId();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const results = usePersons({ q: debounced || undefined, page_size: 8 });
  const items = debounced ? (results.data?.items ?? []) : [];

  if (value) {
    return (
      <div className="flex h-10 items-center justify-between gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm">
        <span className="truncate font-medium text-slate-900">{value.full_name}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-label={`${messages.clear} ${value.full_name}`}
          className="text-lg text-slate-500 hover:text-slate-900"
        >
          ×
        </button>
      </div>
    );
  }

  const pick = (p: PickedPerson) => {
    onChange(p);
    setQ("");
    setOpen(false);
  };

  return (
    <div className="relative">
      <input
        id={id}
        role="combobox"
        aria-expanded={open && debounced.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        value={q}
        placeholder={placeholder ?? messages.personSearchPlaceholder}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, items.length - 1));
          else if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
          else if (e.key === "Enter" && items[active]) {
            e.preventDefault();
            pick(items[active]);
          }
        }}
        className={`h-10 w-full rounded-lg border bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900/20 ${invalid ? "border-overdue" : "border-slate-300"}`}
      />
      {open && debounced && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {items.map((p, i) => (
            <li
              key={p.id}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(p);
              }}
              className={`cursor-pointer px-3 py-2 text-sm ${i === active ? "bg-slate-100" : ""}`}
            >
              {p.full_name}
            </li>
          ))}
          {results.isSuccess && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500">{messages.empty}</li>
          )}
          {onCreateNew && (
            <li
              role="option"
              aria-selected={false}
              onMouseDown={(e) => {
                e.preventDefault();
                onCreateNew(debounced);
                setOpen(false);
              }}
              className="cursor-pointer border-t border-slate-100 px-3 py-2 text-sm font-medium text-teal-800 hover:bg-teal-50"
            >
              + {messages.newMemberNamed.replace("{name}", debounced)}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
