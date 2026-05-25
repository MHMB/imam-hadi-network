/**
 * Typed fetch client.  Stub for P0 — generated types land in P3
 * via `openapi-typescript` against the FastAPI spec.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return (await res.json()) as T;
}
