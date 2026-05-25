import { messages } from "@/lib/i18n";

export function Loading({ label = messages.loading }: { label?: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-sm text-slate-500" role="status">
      {label}
    </div>
  );
}

export function ErrorState({ message = messages.error }: { message?: string }) {
  return (
    <div className="rounded-md bg-overdue-subtle px-4 py-3 text-sm text-overdue" role="alert">
      {message}
    </div>
  );
}

export function EmptyState({ message = messages.empty }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-sm text-slate-500">{message}</div>
  );
}
