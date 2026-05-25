/**
 * Typed API client over the auto-generated OpenAPI schema.
 *
 * Add a new endpoint by extending the generated `paths` (re-run
 * `pnpm gen:api` after the FastAPI side ships a new route) — the
 * helpers below are thin wrappers around `fetch` and inherit the
 * response shape automatically.
 */

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];

// --- selected response aliases (UI imports these instead of indexing components) ---
export type KPIResponse = Schemas["KPIResponse"];
export type KPIByYear = Schemas["KPIByYear"];
export type TopicSummary = Schemas["TopicSummary"];
export type PageOfPersonListItem = Schemas["Page_PersonListItem_"];
export type PersonListItem = Schemas["PersonListItem"];
export type PersonDetailResponse = Schemas["PersonDetailResponse"];
export type PageOfLoanListItem = Schemas["Page_LoanListItem_"];
export type LoanListItem = Schemas["LoanListItem"];
export type LoanDetailResponse = Schemas["LoanDetailResponse"];
export type DataIssueItem = Schemas["DataIssueItem"];
export type ImportListItem = Schemas["ImportListItem"];
export type ImportDetailResponse = Schemas["ImportDetailResponse"];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    message?: string,
  ) {
    super(message ?? `API ${status}: ${path}`);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  // `API_BASE` already ends with `/api`; callers pass paths starting with `/`.
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError(res.status, path);
  }
  return (await res.json()) as T;
}

// --- query-string helper (typed-ish) ---

type QueryValue = string | number | boolean | null | undefined;

function qs(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const out = search.toString();
  return out ? `?${out}` : "";
}

// --- endpoints ---

export const api = {
  kpi: () => getJson<KPIResponse>("/kpi"),

  topics: (params: { year?: number } = {}) =>
    getJson<TopicSummary[]>(`/topics${qs(params)}`),

  persons: (
    params: {
      q?: string;
      verified_only?: boolean;
      has_debt?: boolean;
      has_receivable?: boolean;
      page?: number;
      page_size?: number;
    } = {},
  ) => getJson<PageOfPersonListItem>(`/persons${qs(params)}`),

  person: (id: number) => getJson<PersonDetailResponse>(`/persons/${id}`),

  loans: (
    params: {
      year?: number;
      topic_ids?: string;
      status?: "active" | "settled";
      borrower_id?: number;
      lender_id?: number;
      liaison?: string;
      q?: string;
      page?: number;
      page_size?: number;
    } = {},
  ) => getJson<PageOfLoanListItem>(`/loans${qs(params)}`),

  loan: (id: number) => getJson<LoanDetailResponse>(`/loans/${id}`),

  imports: (params: { page?: number; page_size?: number } = {}) =>
    getJson<Schemas["Page_ImportListItem_"]>(`/imports${qs(params)}`),

  import: (id: number) => getJson<ImportDetailResponse>(`/imports/${id}`),

  issues: (
    params: {
      import_id?: number;
      severity?: "error" | "warning" | "info";
      category?: string;
      page?: number;
      page_size?: number;
    } = {},
  ) => getJson<Schemas["Page_DataIssueItem_"]>(`/issues${qs(params)}`),
};

// Re-export the raw paths type so route-aware code (e.g. hooks generated
// from `paths`) can use it.
export type { paths };
