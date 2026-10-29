import { messages } from "@/lib/i18n";

export type SortDir = "asc" | "desc";

/** Table header that toggles server-side sort; arrow shows the active direction. */
export function SortableTh<K extends string>({
  label,
  sortKey,
  active,
  dir,
  onSort,
}: {
  label: string;
  sortKey: K;
  active: K | null;
  dir: SortDir;
  onSort: (k: K) => void;
}) {
  const isActive = active === sortKey;
  return (
    <th
      className="px-4 py-2 text-start font-medium"
      aria-sort={isActive ? (dir === "asc" ? "ascending" : "descending") : undefined}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        aria-pressed={isActive}
        aria-label={`${messages.sortedBy} ${label}`}
        className="inline-flex items-center gap-1 hover:text-slate-900"
      >
        {label}
        <span aria-hidden className={isActive ? "text-slate-900" : "text-slate-300"}>
          {isActive ? (dir === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  );
}
