"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

type ParamValue = string | number | null | undefined;

/**
 * List filters/sort/page kept in the URL so a filtered view survives reload
 * and can be shared. Empty values are dropped from the query string.
 * Pages using this must render inside <Suspense> (useSearchParams).
 */
export function useUrlParams() {
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const str = (key: string): string => search.get(key) ?? "";
  const num = (key: string): number | "" => {
    const v = search.get(key);
    return v === null || v === "" || Number.isNaN(Number(v)) ? "" : Number(v);
  };

  const set = (patch: Record<string, ParamValue>) => {
    const next = new URLSearchParams(search.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === undefined || v === "") next.delete(k);
      else next.set(k, String(v));
    }
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return { str, num, set };
}
