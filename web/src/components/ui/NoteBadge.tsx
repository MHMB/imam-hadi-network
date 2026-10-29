import { messages } from "@/lib/i18n";

/** Marks a loan that carries a note the admin should read (on the loan page). */
export function NoteBadge() {
  return (
    <span
      title={messages.hasNote}
      aria-label={messages.hasNote}
      role="img"
      className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-amber-100 text-amber-800"
    >
      <svg
        className="h-3 w-3"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
      </svg>
    </span>
  );
}
