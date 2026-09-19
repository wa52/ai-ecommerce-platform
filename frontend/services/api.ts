const API_BASE = process.env.NEXT_PUBLIC_AI_API_URL ?? "http://localhost:8001/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, { ...init, cache: "no-store" });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      // keep default detail
    }
    throw new Error(`请求失败：${detail}`);
  }
  return resp.json() as Promise<T>;
}

export const fetchHealth = () => request<import("@/types/api").HealthResponse>("/health");
export const createTask = (name: string, payload: Record<string, unknown> = {}) =>
  request<import("@/types/api").TaskCreateResponse>("/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, payload }),
  });
export const fetchTaskStatus = (id: string) =>
  request<import("@/types/api").TaskStatus>(`/tasks/${id}`);
