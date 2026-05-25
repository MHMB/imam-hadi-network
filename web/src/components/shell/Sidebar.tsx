"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { messages } from "@/lib/i18n";
import { NAV_ITEMS } from "./nav-items";

export function Sidebar({ className = "" }: { className?: string }) {
  const pathname = usePathname();
  return (
    <aside
      className={`flex flex-col border-l border-slate-200 bg-white ${className}`}
      aria-label={messages.navHome}
    >
      <div className="px-5 py-6">
        <h1 className="text-lg font-bold leading-snug text-slate-900">{messages.appTitle}</h1>
      </div>
      <nav className="flex-1 px-3" aria-label={messages.navHome}>
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={[
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100",
                  ].join(" ")}
                  aria-current={active ? "page" : undefined}
                >
                  <svg
                    className="h-5 w-5 flex-shrink-0"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                  >
                    <path d={item.iconPath} />
                  </svg>
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
