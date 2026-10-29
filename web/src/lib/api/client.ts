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
export type GuarantorOption = Schemas["GuarantorOption"];
export type PageOfLoanListItem = Schemas["Page_LoanListItem_"];
export type LoanListItem = Schemas["LoanListItem"];
export type LoanDetailResponse = Schemas["LoanDetailResponse"];
export type DataIssueItem = Schemas["DataIssueItem"];
export type ImportListItem = Schemas["ImportListItem"];
export type ImportDetailResponse = Schemas["ImportDetailResponse"];
export type OverdueInstallmentItem = Schemas["OverdueInstallmentItem"];
export type PageOfOverdueInstallmentItem = Schemas["Page_OverdueInstallmentItem_"];
export type MonthlyAnalyticsResponse = Schemas["MonthlyAnalyticsResponse"];
export type CirculationResponse = Schemas["CirculationResponse"];
export type CirculationMonth = Schemas["CirculationMonth"];
export type AuditEntry = Schemas["AuditEntry"];
export type LiaisonRow = Schemas["LiaisonRow"];
export type LoanCreate = Schemas["LoanCreate"];
export type LoanUpdate = Schemas["LoanUpdate"];
export type LenderSchedule = SchedulePreview["lenders"][number];
export type SchedulePreview = Schemas["SchedulePreview"];
export type SchedulePreviewRequest = Schemas["SchedulePreviewRequest"];
export type PaymentCreate = Schemas["PaymentCreate"];
export type PaymentOut = Schemas["PaymentOut"];
export type PaymentPreview = Schemas["PaymentPreview"];
export type PersonUpdate = Schemas["PersonUpdate"];
export type ScheduleEdit = Schemas["ScheduleEdit"];
export type Platform = Schemas["ContactRef"]["platform"];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    message?: string,
    /** Per-field Persian messages from a 422 (`detail[].loc` last segment → msg). */
    readonly fields: Record<string, string> = {},
    /** Per-field error codes (e.g. `credit_needs_confirmation`, `duplicate`). */
    readonly codes: Record<string, string> = {},
  ) {
    super(message ?? `API ${status}: ${path}`);
    this.name = "ApiError";
  }
}

// Business-rule errors carry Persian text; pydantic's own (English) ones get a generic line.
const OWN_CODES = new Set(["invalid", "duplicate", "credit_needs_confirmation", "not_found"]);
const GENERIC_INVALID = "مقدار واردشده معتبر نیست.";

async function toApiError(res: Response, path: string): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = ((await res.json()) as { detail?: unknown }).detail;
  } catch {
    detail = undefined;
  }
  if (typeof detail === "string") return new ApiError(res.status, path, detail);
  const fields: Record<string, string> = {};
  const codes: Record<string, string> = {};
  if (Array.isArray(detail)) {
    for (const d of detail as { loc?: (string | number)[]; msg?: string; type?: string }[]) {
      const loc = (d.loc ?? []).filter((p) => p !== "body");
      const key = loc.length ? String(loc[0]) : "_";
      fields[key] ??=
        d.type && OWN_CODES.has(d.type) ? (d.msg ?? GENERIC_INVALID) : GENERIC_INVALID;
      if (d.type) codes[key] ??= d.type;
    }
  }
  return new ApiError(res.status, path, Object.values(fields)[0], fields, codes);
}

async function sendJson<T>(
  method: "POST" | "PUT" | "PATCH",
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw await toApiError(res, path);
  return (await res.json()) as T;
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

  topics: (params: { year?: number } = {}) => getJson<TopicSummary[]>(`/topics${qs(params)}`),

  persons: (
    params: {
      q?: string;
      verified_only?: boolean;
      has_debt?: boolean;
      has_receivable?: boolean;
      guarantor_id?: number;
      sort?: "name" | "lent" | "borrowed" | "net" | "overdue";
      sort_dir?: "asc" | "desc";
      page?: number;
      page_size?: number;
    } = {},
  ) => getJson<PageOfPersonListItem>(`/persons${qs(params)}`),

  guarantorOptions: () => getJson<GuarantorOption[]>("/persons/guarantors"),

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
      due_within_days?: number;
      sort?: "loan_number" | "year" | "total" | "remaining";
      sort_dir?: "asc" | "desc";
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

  overdueInstallments: (
    params: {
      min_days_overdue?: number;
      year?: number;
      /** Jalali YYYY-MM-DD, inclusive */
      due_from?: string;
      due_to?: string;
      page?: number;
      page_size?: number;
    } = {},
  ) => getJson<PageOfOverdueInstallmentItem>(`/installments/overdue${qs(params)}`),

  monthlyAnalytics: (params: { year?: number; month?: number } = {}) =>
    getJson<MonthlyAnalyticsResponse>(`/analytics/monthly${qs(params)}`),

  circulation: () => getJson<CirculationResponse>("/analytics/circulation"),

  // --- writes ---
  me: () => getJson<Schemas["MeResponse"]>("/me"),
  audit: (entity: "loan" | "person" | "payment" | "liaison", entityId: number) =>
    getJson<AuditEntry[]>(`/audit${qs({ entity, entity_id: entityId })}`),
  createPerson: (body: Schemas["PersonCreate"]) =>
    sendJson<Schemas["CreatedResponse"]>("POST", "/persons", body),
  updatePerson: (id: number, body: PersonUpdate) =>
    sendJson<PersonDetailResponse>("PATCH", `/persons/${id}`, body),
  liaisons: () => getJson<LiaisonRow[]>("/liaisons"),
  linkLiaison: (body: Schemas["LiaisonLink"]) => sendJson<LiaisonRow[]>("PUT", "/liaisons", body),
  schedulePreview: (body: SchedulePreviewRequest) =>
    sendJson<SchedulePreview>("POST", "/loans/schedule-preview", body),
  createLoan: (body: LoanCreate) => sendJson<Schemas["CreatedResponse"]>("POST", "/loans", body),
  updateLoan: (id: number, body: LoanUpdate) =>
    sendJson<LoanDetailResponse>("PATCH", `/loans/${id}`, body),
  editSchedule: (id: number, body: ScheduleEdit) =>
    sendJson<LoanDetailResponse>("PUT", `/loans/${id}/schedule`, body),
  payments: (loanId: number) => getJson<PaymentOut[]>(`/loans/${loanId}/payments`),
  paymentPreview: (loanId: number, amount: string) =>
    sendJson<PaymentPreview>("POST", `/loans/${loanId}/payments/preview`, { amount }),
  createPayment: (loanId: number, body: PaymentCreate) =>
    sendJson<PaymentOut[]>("POST", `/loans/${loanId}/payments`, body),
  voidPayment: (paymentId: number) => sendJson<PaymentOut[]>("POST", `/payments/${paymentId}/void`),

  uploadImports: async (files: File[], confirmAppDataLoss = false): Promise<ImportListItem[]> => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    if (confirmAppDataLoss) form.append("confirm_app_data_loss", "true");
    const res = await fetch(`${API_BASE}/imports`, {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      throw new ApiError(res.status, "/imports", await safeError(res));
    }
    return (await res.json()) as ImportListItem[];
  },
};

async function safeError(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // ignore non-json error bodies
  }
  return undefined;
}

// Re-export the raw paths type so route-aware code (e.g. hooks generated
// from `paths`) can use it.
export type { paths };
