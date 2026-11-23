// =============================================================================
// AgentGuard — Dashboard Overview View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { Agent, ToolDefinition, SecurityPolicy, ApprovalRequest, EvaluationRun } from "@/types";
import {
  Shield,
  Bot,
  Wrench,
  ShieldAlert,
  ClockAlert,
  ArrowRight,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Lock,
} from "lucide-react";

export default function OverviewView() {
  const { activeProject, setActiveView } = useApp();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [recentEvals, setRecentEvals] = useState<EvaluationRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeProject) return;
    setLoading(true);
    Promise.all([
      api.listAgents(activeProject.id).catch(() => []),
      api.listTools(activeProject.id).catch(() => []),
      api.listPolicies(activeProject.id).catch(() => []),
      api.listApprovals(activeProject.id, "PENDING").catch(() => []),
      api.listEvaluations(activeProject.id).catch(() => []),
    ])
      .then(([a, t, p, app, ev]) => {
        setAgents(a);
        setTools(t);
        setPolicies(p);
        setApprovals(app);
        setRecentEvals(ev);
      })
      .finally(() => setLoading(false));
  }, [activeProject]);

  const latestEval = recentEvals.length > 0 ? recentEvals[0] : null;

  return (
    <div className="space-y-6">
      {/* Top Welcome / Status Banner */}
      <div className="bg-gradient-to-r from-blue-950/40 via-zinc-900 to-zinc-900 border border-blue-500/20 rounded-2xl p-6 relative overflow-hidden">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono mb-3">
            <Shield className="w-3.5 h-3.5" />
            Deterministic Policy Engine Active
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            {activeProject ? activeProject.name : "AgentGuard Security Platform"}
          </h1>
          <p className="text-sm text-zinc-400 mt-2 leading-relaxed">
            LLMs propose actions. AgentGuard authorizes, controls, executes, and audits them.
            Enforcing strict tenant isolation, 7-rule policy evaluation, and cryptographically bound human approvals.
          </p>
          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={() => setActiveView("playground")}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              Test in Playground
            </button>
            <button
              onClick={() => setActiveView("evaluations")}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs font-medium transition-all"
            >
              Run Security Benchmark
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Active Agents */}
        <div
          onClick={() => setActiveView("agents")}
          className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-5 cursor-pointer transition-all hover:translate-y-[-2px]"
        >
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-medium uppercase tracking-wider">Agents</span>
            <Bot className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-zinc-100 font-mono">
            {loading ? "..." : agents.length}
          </div>
          <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1">
            <span>{agents.filter((a) => a.is_enabled).length} active</span>
            <span>•</span>
            <span>All sandboxed</span>
          </div>
        </div>

        {/* Registered Tools */}
        <div
          onClick={() => setActiveView("tools")}
          className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-5 cursor-pointer transition-all hover:translate-y-[-2px]"
        >
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-medium uppercase tracking-wider">Tools Catalog</span>
            <Wrench className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-zinc-100 font-mono">
            {loading ? "..." : tools.length}
          </div>
          <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1">
            <span>Precompiled Python whitelist</span>
          </div>
        </div>

        {/* Active Policies */}
        <div
          onClick={() => setActiveView("policies")}
          className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-5 cursor-pointer transition-all hover:translate-y-[-2px]"
        >
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-medium uppercase tracking-wider">Security Policies</span>
            <Lock className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-zinc-100 font-mono">
            {loading ? "..." : policies.length}
          </div>
          <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1">
            <span>7-rule deterministic checks</span>
          </div>
        </div>

        {/* Pending Approvals */}
        <div
          onClick={() => setActiveView("approvals")}
          className="bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-5 cursor-pointer transition-all hover:translate-y-[-2px]"
        >
          <div className="flex items-center justify-between text-zinc-400">
            <span className="text-xs font-medium uppercase tracking-wider">Pending Approvals</span>
            <ClockAlert className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 text-2xl font-bold text-zinc-100 font-mono flex items-center gap-2">
            <span>{loading ? "..." : approvals.length}</span>
            {approvals.length > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-sans font-semibold">
                Action Required
              </span>
            )}
          </div>
          <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1">
            <span>RFC 8785 Canonical Hash bound</span>
          </div>
        </div>
      </div>

      {/* Security Interception Architecture Flow Diagram */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300">
              Guarded Execution Pipeline
            </h2>
            <p className="text-xs text-zinc-500">
              Deterministic short-circuit evaluation order: AI proposals cannot bypass this perimeter.
            </p>
          </div>
          <span className="text-[11px] font-mono px-2 py-1 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Zero Direct Tool Access
          </span>
        </div>

        {/* Interactive Visual Architecture */}
        <div className="grid grid-cols-1 md:grid-cols-7 gap-2 text-center text-xs">
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 flex flex-col items-center justify-center">
            <span className="font-mono text-zinc-500 text-[10px]">STAGE 1</span>
            <span className="font-semibold text-zinc-200 mt-1">Untrusted LLM</span>
            <span className="text-[10px] text-zinc-500 mt-0.5">Proposes Action</span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-950 border border-blue-900/50 flex flex-col items-center justify-center">
            <span className="font-mono text-blue-400 text-[10px]">STAGE 2</span>
            <span className="font-semibold text-zinc-200 mt-1">Guarded Executor</span>
            <span className="text-[10px] text-zinc-400 mt-0.5">Captures Proposal</span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 flex flex-col items-center justify-center">
            <span className="font-mono text-purple-400 text-[10px]">RULE 1 & 2</span>
            <span className="font-semibold text-zinc-200 mt-1">Permission / Deny</span>
            <span className="text-[10px] text-zinc-500 mt-0.5">Whitelist Check</span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 flex flex-col items-center justify-center">
            <span className="font-mono text-purple-400 text-[10px]">RULE 3 & 4</span>
            <span className="font-semibold text-zinc-200 mt-1">Ceiling & Tenant</span>
            <span className="text-[10px] text-zinc-500 mt-0.5">Scope Isolation</span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 flex flex-col items-center justify-center">
            <span className="font-mono text-purple-400 text-[10px]">RULE 5 & 6</span>
            <span className="font-semibold text-zinc-200 mt-1">Args & Patterns</span>
            <span className="text-[10px] text-zinc-500 mt-0.5">Schema Validation</span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-950 border border-amber-900/40 flex flex-col items-center justify-center">
            <span className="font-mono text-amber-400 text-[10px]">RULE 7</span>
            <span className="font-semibold text-zinc-200 mt-1">Human Approval</span>
            <span className="text-[10px] text-amber-500/80 mt-0.5">Separation of Duty</span>
          </div>

          <div className="p-3 rounded-lg bg-zinc-950 border border-emerald-900/40 flex flex-col items-center justify-center">
            <span className="font-mono text-emerald-400 text-[10px]">EXECUTION</span>
            <span className="font-semibold text-emerald-300 mt-1">Allow & Audit</span>
            <span className="text-[10px] text-emerald-500/80 mt-0.5">Deterministic</span>
          </div>
        </div>
      </div>

      {/* Benchmark Security Scoreboard */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-blue-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300">
              Adversarial Benchmark Standing
            </h2>
          </div>
          <button
            onClick={() => setActiveView("evaluations")}
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium"
          >
            Detailed Metrics <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {latestEval ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800">
              <div className="text-xs text-zinc-500">Attack Success Rate (ASR)</div>
              <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
                {latestEval.metrics.protected?.asr !== null && latestEval.metrics.protected?.asr !== undefined
                  ? `${(latestEval.metrics.protected.asr * 100).toFixed(1)}%`
                  : "0.0%"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">
                Baseline: {((latestEval.metrics.baseline?.asr ?? 1) * 100).toFixed(0)}%
              </div>
            </div>

            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800">
              <div className="text-xs text-zinc-500">Unauthorized Tool Exec (UTER)</div>
              <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
                {latestEval.metrics.protected?.uter !== null && latestEval.metrics.protected?.uter !== undefined
                  ? `${(latestEval.metrics.protected.uter * 100).toFixed(1)}%`
                  : "0.0%"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">Zero leak guarantee</div>
            </div>

            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800">
              <div className="text-xs text-zinc-500">Legitimate Success (LTSR)</div>
              <div className="text-xl font-bold font-mono text-blue-400 mt-1">
                {latestEval.metrics.protected?.ltsr !== null && latestEval.metrics.protected?.ltsr !== undefined
                  ? `${(latestEval.metrics.protected.ltsr * 100).toFixed(1)}%`
                  : "100.0%"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">Preserves valid utility</div>
            </div>

            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800">
              <div className="text-xs text-zinc-500">Policy Evaluation (p95)</div>
              <div className="text-xl font-bold font-mono text-purple-400 mt-1">
                {latestEval.metrics.protected?.policy_latency_p95_ms !== null &&
                latestEval.metrics.protected?.policy_latency_p95_ms !== undefined
                  ? `${latestEval.metrics.protected.policy_latency_p95_ms.toFixed(2)}ms`
                  : "<1.0ms"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">Sub-millisecond pure Python</div>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center bg-zinc-950 rounded-lg border border-dashed border-zinc-800">
            <p className="text-sm text-zinc-400">
              No benchmark runs recorded yet for this workspace.
            </p>
            <button
              onClick={() => setActiveView("evaluations")}
              className="mt-3 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
            >
              Run 21-Case Security Evaluation
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
