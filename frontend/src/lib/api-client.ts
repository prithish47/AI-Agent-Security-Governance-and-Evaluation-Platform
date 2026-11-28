// =============================================================================
// AgentGuard — Comprehensive Typed API Client
// =============================================================================
// Token Storage Design & Security Trade-Offs:
// - Short-lived access tokens are held strictly in JavaScript memory (never
//   persisted to localStorage) to prevent long-lived storage exposure.
// - Rotating refresh tokens are stored in per-tab sessionStorage so page
//   reloads within the same tab restore the session via /api/v1/auth/refresh,
//   while separate tabs maintain independent session families (avoiding false
//   rotation reuse collisions) and closing the tab clears the refresh token.
// - Note: Because frontend (localhost:3000) and backend (localhost:8000) run on
//   separate origins with Bearer auth, HttpOnly cookies are not used yet; XSS
//   mitigation (CSP, sanitization) remains essential while tokens exist in JS.
// =============================================================================

import type {
  Agent,
  ApprovalRequest,
  AuditEvent,
  EvaluationResult,
  EvaluationRun,
  Execution,
  ExecutionTrace,
  PolicyVersion,
  Project,
  ProjectMember,
  SecurityPolicy,
  ToolDefinition,
  User,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const REFRESH_STORAGE_KEY = "ag_refresh_token";
const LEGACY_ACCESS_STORAGE_KEY = "ag_access_token";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, message: string, code: string = "UNKNOWN_ERROR") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// -----------------------------------------------------------------------------
// Token Storage & Single-Flight Refresh Coordinator
// -----------------------------------------------------------------------------

let memoryAccessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;
let authFailureHandler: (() => void) | null = null;

function getSessionStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return memoryAccessToken;
}

export function getRefreshToken(): string | null {
  const storage = getSessionStorage();
  return storage ? storage.getItem(REFRESH_STORAGE_KEY) : null;
}

export function hasRefreshToken(): boolean {
  return Boolean(getRefreshToken());
}

export function setSessionTokens(accessToken: string, refreshToken: string): void {
  memoryAccessToken = accessToken;
  const storage = getSessionStorage();
  if (storage) {
    storage.setItem(REFRESH_STORAGE_KEY, refreshToken);
  }
}

export function clearSessionTokens(): void {
  memoryAccessToken = null;
  const storage = getSessionStorage();
  if (storage) {
    storage.removeItem(REFRESH_STORAGE_KEY);
  }
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(LEGACY_ACCESS_STORAGE_KEY);
      window.localStorage.removeItem(REFRESH_STORAGE_KEY);
    } catch {
      // Ignore storage access errors
    }
  }
}

export function setAuthFailureHandler(handler: (() => void) | null): void {
  authFailureHandler = handler;
}

const SKIP_REFRESH_ENDPOINTS = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/refresh",
  "/api/v1/auth/logout",
  "/health",
  "/api/v1/",
]);

export async function refreshAccessTokenSingleFlight(): Promise<string | null> {
  if (!refreshPromise) {
    const currentRefresh = getRefreshToken();
    if (!currentRefresh) {
      clearSessionTokens();
      return null;
    }

    let inFlight: Promise<string | null> | null = null;
    inFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: currentRefresh }),
        });

        if (!res.ok) {
          clearSessionTokens();
          return null;
        }

        const data = await res.json();
        if (!data?.access_token || !data?.refresh_token) {
          clearSessionTokens();
          return null;
        }

        setSessionTokens(data.access_token, data.refresh_token);
        return data.access_token as string;
      } catch {
        clearSessionTokens();
        return null;
      } finally {
        if (refreshPromise === inFlight) {
          refreshPromise = null;
        }
      }
    })();
    refreshPromise = inFlight;
  }
  return refreshPromise;
}

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  isRetry: boolean = false
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const sentToken = getAccessToken();
  if (sentToken && !SKIP_REFRESH_ENDPOINTS.has(endpoint)) {
    headers["Authorization"] = `Bearer ${sentToken}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 && !isRetry && !SKIP_REFRESH_ENDPOINTS.has(endpoint)) {
    // If another concurrent request already rotated the access token, retry with it
    const latestToken = getAccessToken();
    if (latestToken && latestToken !== sentToken) {
      return apiFetch<T>(endpoint, options, true);
    }

    const refreshedToken = await refreshAccessTokenSingleFlight();
    if (refreshedToken) {
      return apiFetch<T>(endpoint, options, true);
    }

    clearSessionTokens();
    if (authFailureHandler) {
      authFailureHandler();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message = body?.detail?.message || body?.detail || "An unexpected error occurred";
    const code = body?.detail?.code || "ERROR";
    throw new ApiError(response.status, message, code);
  }

  return body as T;
}

export const api = {
  // System
  health: () => apiFetch<{ status: string; version: string; database: string }>("/health"),
  apiRoot: () => apiFetch<{ api: string; version: string; status: string }>("/api/v1/"),

  // Authentication
  register: (data: { email: string; username: string; password: string }) =>
    apiFetch<User>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    apiFetch<{ access_token: string; refresh_token: string; expires_in: number }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  refresh: () => refreshAccessTokenSingleFlight(),

  getMe: () => apiFetch<User>("/api/v1/auth/me"),

  logout: (refreshToken: string) =>
    apiFetch<{ message: string }>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  // Projects
  listProjects: () => apiFetch<Project[]>("/api/v1/projects"),
  createProject: (data: { name: string; description?: string }) =>
    apiFetch<Project>("/api/v1/projects", { method: "POST", body: JSON.stringify(data) }),
  getProject: (id: string) => apiFetch<Project>(`/api/v1/projects/${id}`),
  updateProject: (id: string, data: { name?: string; description?: string }) =>
    apiFetch<Project>(`/api/v1/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteProject: (id: string) => apiFetch<void>(`/api/v1/projects/${id}`, { method: "DELETE" }),
  listMembers: (projectId: string) => apiFetch<ProjectMember[]>(`/api/v1/projects/${projectId}/members`),

  // Agents
  listAgents: (projectId: string) => apiFetch<Agent[]>(`/api/v1/projects/${projectId}/agents`),
  createAgent: (projectId: string, data: Partial<Agent>) =>
    apiFetch<Agent>(`/api/v1/projects/${projectId}/agents`, { method: "POST", body: JSON.stringify(data) }),
  getAgent: (agentId: string) => apiFetch<Agent>(`/api/v1/agents/${agentId}`),
  updateAgent: (agentId: string, data: Partial<Agent>) =>
    apiFetch<Agent>(`/api/v1/agents/${agentId}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAgent: (agentId: string) => apiFetch<void>(`/api/v1/agents/${agentId}`, { method: "DELETE" }),
  assignTool: (agentId: string, toolId: string) =>
    apiFetch<any>(`/api/v1/agents/${agentId}/tools`, { method: "POST", body: JSON.stringify({ tool_id: toolId }) }),
  unassignTool: (agentId: string, toolId: string) =>
    apiFetch<void>(`/api/v1/agents/${agentId}/tools/${toolId}`, { method: "DELETE" }),

  // Tools
  listTools: (projectId: string) => apiFetch<ToolDefinition[]>(`/api/v1/projects/${projectId}/tools`),
  createTool: (projectId: string, data: Partial<ToolDefinition>) =>
    apiFetch<ToolDefinition>(`/api/v1/projects/${projectId}/tools`, { method: "POST", body: JSON.stringify(data) }),
  updateTool: (toolId: string, data: Partial<ToolDefinition>) =>
    apiFetch<ToolDefinition>(`/api/v1/tools/${toolId}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteTool: (toolId: string) => apiFetch<void>(`/api/v1/tools/${toolId}`, { method: "DELETE" }),

  // Policies
  listPolicies: (projectId: string) => apiFetch<SecurityPolicy[]>(`/api/v1/projects/${projectId}/policies`),
  createPolicy: (projectId: string, data: { name: string; description?: string; rules: Record<string, any> }) =>
    apiFetch<SecurityPolicy>(`/api/v1/projects/${projectId}/policies`, { method: "POST", body: JSON.stringify(data) }),
  listPolicyVersions: (policyId: string) => apiFetch<PolicyVersion[]>(`/api/v1/policies/${policyId}/versions`),
  createPolicyVersion: (policyId: string, rules: Record<string, any>) =>
    apiFetch<PolicyVersion>(`/api/v1/policies/${policyId}/versions`, { method: "POST", body: JSON.stringify({ rules }) }),
  activatePolicyVersion: (policyId: string, versionId: string) =>
    apiFetch<PolicyVersion>(`/api/v1/policies/${policyId}/activate`, {
      method: "POST",
      body: JSON.stringify({ version_id: versionId }),
    }),

  // Executions
  executeAgent: (agentId: string, task: string) =>
    apiFetch<Execution>(`/api/v1/agents/${agentId}/execute`, { method: "POST", body: JSON.stringify({ task }) }),
  getExecution: (executionId: string) => apiFetch<Execution>(`/api/v1/executions/${executionId}`),
  getExecutionTrace: (executionId: string) => apiFetch<ExecutionTrace>(`/api/v1/executions/${executionId}/trace`),

  // Approvals
  listApprovals: (projectId: string, status?: string) => {
    const qs = status ? `?status=${status}` : "";
    return apiFetch<ApprovalRequest[]>(`/api/v1/projects/${projectId}/approvals${qs}`);
  },
  approveAction: (approvalId: string, note?: string) =>
    apiFetch<ApprovalRequest>(`/api/v1/approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  rejectAction: (approvalId: string, note?: string) =>
    apiFetch<ApprovalRequest>(`/api/v1/approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  resumeApprovedAction: (approvalId: string) =>
    apiFetch<Execution>(`/api/v1/approvals/${approvalId}/resume`, { method: "POST" }),

  // Evaluations
  listEvaluations: (projectId: string) => apiFetch<EvaluationRun[]>(`/api/v1/projects/${projectId}/evaluations`),
  runEvaluation: (projectId: string, agentId: string, mode: "baseline" | "protected" | "both" = "both") =>
    apiFetch<EvaluationRun>(`/api/v1/projects/${projectId}/evaluations/run`, {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId, mode }),
    }),
  getEvaluationResults: (evaluationId: string) =>
    apiFetch<EvaluationResult[]>(`/api/v1/evaluations/${evaluationId}/results`),

  // Audit Logs
  listAuditLogs: (projectId: string, page: number = 1, pageSize: number = 50, filters?: Record<string, string>) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), ...filters });
    return apiFetch<{ items: AuditEvent[]; total: number; page: number; page_size: number }>(
      `/api/v1/projects/${projectId}/audit-logs?${params.toString()}`
    );
  },
};

export default api;
