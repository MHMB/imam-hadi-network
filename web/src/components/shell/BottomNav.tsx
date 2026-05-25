"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "./nav-items";

export function BottomNav({ className = "" }: { className?: string }) {
  const pathname = usePathname();
  return (
    <nav
      className={`fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white shadow-lg ${className}`}
      aria-label="نوار پیمایش"
    >
      <ul className="grid grid-cols-5">
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
                  "flex flex-col items-center gap-1 py-3 text-xs font-medium transition-colors",
                  active ? "text-slate-900" : "text-slate-500 hover:text-slate-700",
                ].join(" ")}
                aria-current={active ? "page" : undefined}
              >
                <svg
                  className="h-6 w-6"
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
  );
}
