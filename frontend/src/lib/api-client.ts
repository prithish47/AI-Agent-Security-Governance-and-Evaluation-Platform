// =============================================================================
// AgentGuard — API Client
// =============================================================================
// Centralized HTTP client for communicating with the FastAPI backend.
//
// WHY A CENTRALIZED CLIENT?
// 1. Single place to configure the base URL
// 2. Automatic JWT token injection for authenticated requests
// 3. Consistent error handling across all API calls
// 4. Type-safe request/response handling
// 5. Easy to add interceptors (logging, retry, etc.)
// =============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Custom error class for API errors.
 * Contains the HTTP status code and the error response body.
 */
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

/**
 * Get the stored access token from localStorage.
 * Returns null if not authenticated.
 */
function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

/**
 * Core fetch wrapper that handles:
 * - Base URL prepending
 * - JWT token injection
 * - JSON serialization/deserialization
 * - Error response parsing
 */
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Build headers
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  
  // Add auth token if available
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
  });
  
  // Handle no-content responses (204)
  if (response.status === 204) {
    return undefined as T;
  }
  
  // Parse response body
  const body = await response.json().catch(() => null);
  
  // Handle error responses
  if (!response.ok) {
    const message = body?.detail?.message || body?.detail || "An error occurred";
    const code = body?.detail?.code || "UNKNOWN_ERROR";
    throw new ApiError(response.status, message, code);
  }
  
  return body as T;
}

// =============================================================================
// Typed API methods
// =============================================================================

export const api = {
  // Health check (no auth required)
  health: () => apiFetch<{ status: string; version: string; database: string }>("/health"),
  
  // API root
  apiRoot: () => apiFetch<{ api: string; version: string; status: string }>("/api/v1/"),
  
  // Auth endpoints will be added in Phase 4
  // Project endpoints will be added in Phase 2
  // Agent endpoints will be added in Phase 2
  // ... etc.
};

export default api;
