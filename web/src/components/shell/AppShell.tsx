"use client";

import { type ReactNode, useEffect, useState } from "react";

import { messages } from "@/lib/i18n";

import { BottomNav } from "./BottomNav";
import { Sidebar } from "./Sidebar";

const STORAGE_KEY = "sidebar-open";

/**
 * Two-column app shell, responsive.
 *
 * - **Mobile** (<md): main scroll area + fixed bottom-tab navigation.
 * - **Desktop** (≥md): right-side sidebar (RTL: starts on the right) +
 *   main scroll area.  The menu button hides / shows the sidebar; hidden,
 *   the page takes the full width.  The choice is remembered per browser.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "0") setOpen(false);
    } catch {
      // storage blocked: keep the default
    }
  }, []);

  const toggle = () =>
    setOpen((o) => {
      try {
        localStorage.setItem(STORAGE_KEY, o ? "0" : "1");
      } catch {
        // ignore
      }
      return !o;
    });

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls="app-sidebar"
        aria-label={open ? messages.menuHide : messages.menuShow}
        title={open ? messages.menuHide : messages.menuShow}
        className="fixed start-3 top-3 z-40 hidden h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50 md:inline-flex"
      >
        <svg
          className="h-5 w-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      {open && (
        <Sidebar id="app-sidebar" className="hidden md:flex md:w-64 md:flex-shrink-0 md:pt-12" />
      )}
      <main className="min-w-0 flex-1 pb-20 md:pb-0">
        <div
          className={`mx-auto px-4 py-6 md:px-6 md:py-10 ${open ? "max-w-6xl" : "max-w-7xl md:ps-16"}`}
        >
          {children}
        </div>
      </main>
      <BottomNav className="md:hidden" />
    </div>
  );
}
