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
