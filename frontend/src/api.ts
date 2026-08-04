export type JobStatus = "pending" | "decomposing" | "generating" | "validating" | "assembling" | "exporting" | "completed" | "failed" | "cancelled";

export interface Job {
  job_id: string;
  status: JobStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  result_url: string | null;
  preview_url: string | null;
  error_message: string | null;
  cost_estimate_usd: number;
  cost_actual_usd: number;
  metadata: Record<string, unknown>;
}

export interface CreateJobPayload {
  prompt: string;
  mode: "3d_model";
  detail_level: "low" | "medium" | "high";
  model_source?: "local" | "remote" | "auto";
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  user: { id: string; email: string; is_active: boolean; created_at: string };
  access_token: string;
  token_type: string;
  expires_in: number;
}

const TOKEN_KEY = "gvs_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}, authed = false): Promise<T> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };
  if (!(init.body instanceof FormData) && init.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (authed) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(path, { ...init, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.message) detail = body.message;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

export async function register(email: string, password: string): Promise<UserResponse> {
  return request<UserResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const body = new URLSearchParams({ username: email, password });
  const resp = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const b = await resp.json();
      if (typeof b.detail === "string") detail = b.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as AuthResponse;
}

export async function me(): Promise<UserResponse["user"]> {
  return request<UserResponse["user"]>("/api/v1/users/me", { method: "GET" }, true);
}

export async function createJob(payload: CreateJobPayload): Promise<Job> {
  return request<Job>("/api/v1/jobs/", { method: "POST", body: JSON.stringify(payload) }, true);
}

export async function getJob(id: string): Promise<Job> {
  return request<Job>(`/api/v1/jobs/${id}`, { method: "GET" }, true);
}

export async function listJobs(): Promise<Job[]> {
  return request<Job[]>("/api/v1/jobs/", { method: "GET" }, true);
}

export async function cancelJob(id: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/v1/jobs/${id}/cancel`, { method: "POST" }, true);
}

export async function deleteJob(id: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/api/v1/jobs/${id}`, { method: "DELETE" }, true);
}

export async function fetchArtifact(id: string, kind: "model" | "preview"): Promise<ArrayBuffer> {
  const token = getToken();
  const resp = await fetch(`/api/v1/jobs/${id}/artifact/${kind}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) throw new ApiError(resp.status, `HTTP ${resp.status}`);
  return resp.arrayBuffer();
}

export const ACTIVE_STATUSES: JobStatus[] = [
  "pending",
  "decomposing",
  "generating",
  "validating",
  "assembling",
  "exporting",
];
