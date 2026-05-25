/**
 * Persian (fa-IR) string catalog — single source of truth for UI copy.
 *
 * All visible UI text routes through this map.  No English in the rendered
 * DOM (DESIGN.md §6.4).  The full glossary lives at DESIGN.md §6.5; this
 * file grows as pages land in P5.
 *
 * Convention: keys are English camelCase identifiers.  Values are Persian.
 */
export const messages = {
  // App-level
  appTitle: "داشبورد شبکه قرض‌الحسنه امام هادی",
  appDescription: "نمایش وضعیت قرض‌ها، افراد و موضوعات",

  // Bootstrap / placeholder
  bootstrapWelcome: "این صفحه به‌زودی فعال می‌شود.",
  phaseStub: "در حال توسعه — فاز ۰ (راه‌اندازی پروژه).",

  // Generic
  loading: "در حال بارگذاری...",
  empty: "موردی یافت نشد",
  error: "خطا در دریافت اطلاعات",
  retry: "تلاش دوباره",
} as const;

export type MessageKey = keyof typeof messages;
