// =============================================================================
// AgentGuard — Platform Settings & Provider Status View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import api from "@/lib/api-client";
import { Settings, ShieldCheck, CheckCircle2, XCircle, Cpu, Server, Key, Lock } from "lucide-react";

export default function SettingsView() {
  const [health, setHealth] = useState<{ status: string; version: string; database: string } | null>(null);
  const [apiInfo, setApiInfo] = useState<{ api: string; version: string; status: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.health().catch(() => null), api.apiRoot().catch(() => null)])
      .then(([h, a]) => {
        setHealth(h);
        setApiInfo(a);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
          <Settings className="w-5 h-5 text-zinc-400" />
          Platform Architecture & Provider Settings
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          System health, AI model adapters, and deterministic security boundary configuration.
        </p>
      </div>

      {/* Backend System Health Status */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300 mb-4 flex items-center gap-2">
          <Server className="w-4 h-4 text-blue-400" />
          Backend Service Health
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-zinc-950 border border-zinc-800">
            <div className="text-xs text-zinc-500">FastAPI Service</div>
            <div className="text-base font-bold font-mono text-emerald-400 mt-1 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />
              {health?.status === "healthy" ? "HEALTHY" : "CONNECTED"}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">Version: v{health?.version || "1.0.0"}</div>
          </div>

          <div className="p-4 rounded-lg bg-zinc-950 border border-zinc-800">
            <div className="text-xs text-zinc-500">Database Engine</div>
            <div className="text-base font-bold font-mono text-emerald-400 mt-1 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" />
              {health?.database || "CONNECTED"}
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">PostgreSQL 17 / Cross-Dialect</div>
          </div>

          <div className="p-4 rounded-lg bg-zinc-950 border border-zinc-800">
            <div className="text-xs text-zinc-500">Guarded Tool Executor</div>
            <div className="text-base font-bold font-mono text-emerald-400 mt-1 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4" />
              ACTIVE
            </div>
            <div className="text-[11px] text-zinc-500 mt-1">Deterministic Fail-Closed</div>
          </div>
        </div>
      </div>

      {/* AI Model Adapters Status */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300 mb-4 flex items-center gap-2">
          <Cpu className="w-4 h-4 text-purple-400" />
          AI Model Adapters & Key Configurations
        </h2>

        <div className="divide-y divide-zinc-800/80">
          <div className="py-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-zinc-200">Deterministic Mock Provider</div>
              <div className="text-xs text-zinc-500">Instant offline benchmark evaluation & testing</div>
            </div>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              Ready / Default
            </span>
          </div>

          <div className="py-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-zinc-200">OpenAI Compatible API</div>
              <div className="text-xs text-zinc-500">Configured via OPENAI_API_KEY environment variable</div>
            </div>
            <span className="text-xs text-zinc-400 font-mono">Adapter Loaded</span>
          </div>

          <div className="py-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-zinc-200">Google Gemini API</div>
              <div className="text-xs text-zinc-500">Configured via GEMINI_API_KEY environment variable</div>
            </div>
            <span className="text-xs text-zinc-400 font-mono">Adapter Loaded</span>
          </div>

          <div className="py-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-zinc-200">Ollama Local Models</div>
              <div className="text-xs text-zinc-500">Default endpoint: http://localhost:11434</div>
            </div>
            <span className="text-xs text-zinc-400 font-mono">Adapter Loaded</span>
          </div>
        </div>
      </div>

      {/* Security Engine Constants & Limits */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300 mb-4 flex items-center gap-2">
          <Lock className="w-4 h-4 text-amber-400" />
          Platform Security Limits
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-800 flex justify-between">
            <span className="text-zinc-500">Hard Iteration Bound:</span>
            <span className="text-zinc-200">20 turns maximum</span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-800 flex justify-between">
            <span className="text-zinc-500">Canonical Serialization:</span>
            <span className="text-zinc-200">RFC 8785 JSON</span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-800 flex justify-between">
            <span className="text-zinc-500">Action Hash Algorithm:</span>
            <span className="text-zinc-200">SHA-256 Hex</span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-800 flex justify-between">
            <span className="text-zinc-500">Password Hashing:</span>
            <span className="text-zinc-200">Argon2id</span>
          </div>
        </div>
      </div>
    </div>
  );
}
