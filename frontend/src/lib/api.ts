// Gọi API /api/v1: bọc {data, meta}/{error}; access token giữ trong bộ nhớ, refresh token ở cookie HttpOnly.
import { useAuth } from "./auth";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: { field?: string; message: string }[] = []) {
    super(message);
  }
}

export interface Envelope<T> { data: T; meta: Record<string, unknown> & { request_id: string; next_cursor?: string | null } }

let refreshing: Promise<boolean> | null = null;

export async function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
      if (!res.ok) { useAuth.getState().clear(); return false; }
      const body = await res.json();
      useAuth.getState().setSession(body.data.access_token, body.data.user);
      return true;
    } catch { return false; } finally { setTimeout(() => { refreshing = null; }, 0); }
  })();
  return refreshing;
}

type Opts = { method?: string; body?: unknown; idempotent?: boolean; query?: Record<string, string | number | undefined | null> };

export async function request<T>(path: string, opts: Opts = {}, retry = true): Promise<Envelope<T>> {
  const url = new URL(`${BASE}/api/v1${path}`, window.location.origin);
  Object.entries(opts.query ?? {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v)); });
  const headers: Record<string, string> = {};
  const token = useAuth.getState().token;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
  let res: Response;
  try {
    res = await fetch(url, { method: opts.method ?? "GET", headers, credentials: "include",
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined });
  } catch {
    throw new ApiError(0, "NETWORK", "Không kết nối được máy chủ. Kiểm tra mạng hoặc thử lại sau.");
  }
  if (res.status === 401 && retry && token && await refreshSession()) return request<T>(path, opts, false);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error;
    throw new ApiError(res.status, e?.code ?? "ERROR", e?.message ?? `Lỗi ${res.status}`, e?.details ?? []);
  }
  return body as Envelope<T>;
}

export const api = {
  get: <T>(path: string, query?: Opts["query"]) => request<T>(path, { query }).then((r) => r.data),
  page: <T>(path: string, query?: Opts["query"]) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, idempotent = false) => request<T>(path, { method: "POST", body: body ?? {}, idempotent }).then((r) => r.data),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }).then((r) => r.data),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body }).then((r) => r.data),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }).then((r) => r.data),
};

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.details.length ? `${e.message} ${e.details.map((d) => d.message).join("; ")}` : e.message;
  return "Đã có lỗi xảy ra.";
}
