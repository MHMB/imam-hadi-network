import type { ReactNode } from "react";

import { BottomNav } from "./BottomNav";
import { Sidebar } from "./Sidebar";

/**
 * Two-column app shell, responsive.
 *
 * - **Mobile** (<md): main scroll area + fixed bottom-tab navigation.
 * - **Desktop** (≥md): right-side sidebar (RTL: starts on the right) +
 *   main scroll area.  Mobile bottom-nav is hidden.
 *
 * RTL is set at the `<html>` level in `layout.tsx`; Tailwind's logical
 * utilities + the `tailwindcss-rtl` plugin do the rest.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <Sidebar className="hidden md:flex md:w-64 md:flex-shrink-0" />
      <main className="flex-1 pb-20 md:pb-0">
        <div className="mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-10">{children}</div>
      </main>
      <BottomNav className="md:hidden" />
    </div>
  );
}
