// =============================================================================
// AgentGuard — Frontend Landing Page
// =============================================================================
// This is the initial page shown when the frontend loads.
// It verifies connectivity to the backend API.
// Will be replaced with the login/dashboard in Phase 9.
// =============================================================================

"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api-client";

interface HealthStatus {
  status: string;
  version: string;
  database: string;
}

export default function Home() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .health()
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to connect to backend");
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
      <div className="max-w-lg w-full mx-auto p-8">
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 mb-4">
            <svg
              className="w-8 h-8 text-blue-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">AgentGuard</h1>
          <p className="text-zinc-400 mt-2">
            AI Agent Security & Reliability Platform
          </p>
        </div>

        {/* Connection Status */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-4">
            System Status
          </h2>

          {loading && (
            <div className="flex items-center gap-3 text-zinc-400">
              <div className="w-4 h-4 border-2 border-zinc-600 border-t-blue-500 rounded-full animate-spin" />
              Connecting to backend...
            </div>
          )}

          {error && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-red-400">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                Backend Unavailable
              </div>
              <p className="text-sm text-zinc-500">{error}</p>
              <p className="text-xs text-zinc-600">
                Make sure the backend is running at{" "}
                <code className="text-zinc-400">http://localhost:8000</code>
              </p>
            </div>
          )}

          {health && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-zinc-400">API Status</span>
                <span className="flex items-center gap-2">
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${
                      health.status === "healthy"
                        ? "bg-emerald-500"
                        : "bg-yellow-500"
                    }`}
                  />
                  <span
                    className={
                      health.status === "healthy"
                        ? "text-emerald-400"
                        : "text-yellow-400"
                    }
                  >
                    {health.status}
                  </span>
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-zinc-400">Database</span>
                <span className="flex items-center gap-2">
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${
                      health.database === "connected"
                        ? "bg-emerald-500"
                        : "bg-red-500"
                    }`}
                  />
                  <span
                    className={
                      health.database === "connected"
                        ? "text-emerald-400"
                        : "text-red-400"
                    }
                  >
                    {health.database}
                  </span>
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-zinc-400">Version</span>
                <span className="text-zinc-300 font-mono text-sm">
                  v{health.version}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-zinc-600 mt-6">
          Phase 1 — Foundation Verified
        </p>
      </div>
    </div>
  );
}
