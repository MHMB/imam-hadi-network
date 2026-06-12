"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

/**
 * Per-endpoint React Query hooks.
 *
 * Naming: every key starts with the endpoint root so invalidations are easy
 * (`['persons', ...]` invalidates the entire person tree at once).
 */

export function useKpi() {
  return useQuery({ queryKey: ["kpi"], queryFn: api.kpi });
}

export function useTopics(year?: number) {
  return useQuery({
    queryKey: ["topics", year ?? null],
    queryFn: () => api.topics({ year }),
  });
}

export function usePersons(params: Parameters<typeof api.persons>[0] = {}) {
  return useQuery({
    queryKey: ["persons", params],
    queryFn: () => api.persons(params),
  });
}

export function usePerson(id: number | null | undefined) {
  return useQuery({
    queryKey: ["persons", id],
    queryFn: () => api.person(id as number),
    enabled: id != null,
  });
}

export function useLoans(params: Parameters<typeof api.loans>[0] = {}, enabled = true) {
  return useQuery({
    queryKey: ["loans", params],
    queryFn: () => api.loans(params),
    enabled,
  });
}

export function useLoan(id: number | null | undefined) {
  return useQuery({
    queryKey: ["loans", id],
    queryFn: () => api.loan(id as number),
    enabled: id != null,
  });
}

export function useImports(params: Parameters<typeof api.imports>[0] = {}) {
  return useQuery({
    queryKey: ["imports", params],
    queryFn: () => api.imports(params),
  });
}

export function useIssues(params: Parameters<typeof api.issues>[0] = {}) {
  return useQuery({
    queryKey: ["issues", params],
    queryFn: () => api.issues(params),
  });
}

export function useOverdueInstallments(params: Parameters<typeof api.overdueInstallments>[0] = {}) {
  return useQuery({
    queryKey: ["overdue", params],
    queryFn: () => api.overdueInstallments(params),
  });
}

export function useMonthlyAnalytics(year?: number, month?: number) {
  return useQuery({
    queryKey: ["analytics", "monthly", year ?? null, month ?? null],
    queryFn: () => api.monthlyAnalytics({ year, month }),
  });
}

export function useCirculation() {
  return useQuery({ queryKey: ["analytics", "circulation"], queryFn: api.circulation });
}

/** Status-poll hook: refetches every 1.5s while the row is non-terminal. */
export function useImportPolling(id: number | null | undefined) {
  return useQuery({
    queryKey: ["imports", id],
    queryFn: () => api.import(id as number),
    enabled: id != null,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "success" || s === "failed" ? false : 1500;
    },
  });
}

/** Upload mutation: returns the rows the server queued / deduped. */
export function useUploadImports() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => api.uploadImports(files),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["imports"] });
    },
  });
}
