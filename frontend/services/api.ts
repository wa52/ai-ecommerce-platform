const API_BASE = process.env.NEXT_PUBLIC_AI_API_URL ?? "http://localhost:8001/api/v1";
const TOKEN_KEY = "ai_platform_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep default detail
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export interface CheckResult {
  name: string;
  ok: boolean;
  detail: string;
}

export interface HealthResponse {
  status: string;
  postgres: CheckResult;
  redis: CheckResult;
  saleor: CheckResult;
}

export interface TaskCreateResponse {
  id: string;
  name: string;
  status: string;
}

export interface TaskStatus {
  id: string;
  task: string;
  status: "queued" | "success" | "failed";
  result?: Record<string, unknown> | null;
  error?: string | null;
  duration_ms?: number | null;
}

export interface LoginResponse {
  token: string;
  refresh_token: string | null;
  user: { id: string; email: string; is_staff: boolean; permissions: string[] };
}

export const fetchHealth = () => request<HealthResponse>("/health");
export const createTask = (name: string, payload: Record<string, unknown> = {}) =>
  request<TaskCreateResponse>("/tasks", { method: "POST", body: JSON.stringify({ name, payload }) });
export const fetchTaskStatus = (id: string) => request<TaskStatus>(`/tasks/${id}`);
export const login = (email: string, password: string) =>
  request<LoginResponse>("/iam/login", { method: "POST", body: JSON.stringify({ email, password }) });
export const fetchMe = () => request<LoginResponse["user"]>("/iam/me");
