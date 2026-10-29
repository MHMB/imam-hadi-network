import { messages } from "@/lib/i18n";

export interface NavItem {
  href: string;
  label: string;
  /** Lightweight inline SVG path string; rendered inside <svg viewBox="0 0 24 24">. */
  iconPath: string;
}

// Heroicons-style 24x24 outlines.  Kept inline so we don't pull in an icon lib.
export const NAV_ITEMS: readonly NavItem[] = [
  {
    href: "/",
    label: messages.navHome,
    iconPath: "M3 12l9-9 9 9M5 10v10h14V10",
  },
  {
    href: "/persons",
    label: messages.navPeople,
    iconPath:
      "M17 21v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zm6 0a4 4 0 100-8",
  },
  {
    href: "/loans",
    label: messages.navLoans,
    iconPath: "M12 8c-2 0-4 1-4 3s2 3 4 3 4 1 4 3-2 3-4 3m0-12V4m0 16v2",
  },
  {
    href: "/admin/overdue",
    label: messages.navOverdue,
    iconPath: "M12 8v4l3 3M12 21a9 9 0 100-18 9 9 0 000 18z",
  },
  {
    href: "/topics",
    label: messages.navTopics,
    iconPath: "M4 6h16M4 12h16M4 18h7",
  },
  {
    href: "/admin",
    label: messages.navAdmin,
    iconPath: "M12 4v16m8-8H4",
  },
] as const;

/** The nav item for a path: the longest href that matches, so /admin/overdue
 * highlights «معوقات», not «مدیریت». */
export function activeNavHref(pathname: string): string | undefined {
  return NAV_ITEMS.map((i) => i.href)
    .filter((h) => (h === "/" ? pathname === "/" : pathname === h || pathname.startsWith(`${h}/`)))
    .sort((a, b) => b.length - a.length)[0];
}
