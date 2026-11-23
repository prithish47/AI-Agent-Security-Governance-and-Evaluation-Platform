// =============================================================================
// AgentGuard — Evaluations & Adversarial Benchmarks View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { Agent, EvaluationRun, EvaluationResult, BenchmarkMetrics } from "@/types";
import {
  BarChart3,
  ShieldAlert,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  ShieldCheck,
  Zap,
} from "lucide-react";

export default function EvaluationsView() {
  const { activeProject, showToast } = useApp();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [evalMode, setEvalMode] = useState<"both" | "protected" | "baseline">("both");
  const [running, setRunning] = useState(false);
  const [evalRuns, setEvalRuns] = useState<EvaluationRun[]>([]);
  const [activeRun, setActiveRun] = useState<EvaluationRun | null>(null);
  const [results, setResults] = useState<EvaluationResult[]>([]);
  const [loadingResults, setLoadingResults] = useState(false);

  const loadRuns = async () => {
    if (!activeProject) return;
    try {
      const runs = await api.listEvaluations(activeProject.id);
      setEvalRuns(runs);
      if (runs.length > 0 && !activeRun) {
        setActiveRun(runs[0]);
      }
    } catch {
      // Ignored
    }
  };

  useEffect(() => {
    if (!activeProject) return;
    api
      .listAgents(activeProject.id)
      .then((data) => {
        setAgents(data);
        if (data.length > 0 && !selectedAgentId) {
          setSelectedAgentId(data[0].id);
        }
      })
      .catch(() => {});
    loadRuns();
  }, [activeProject]);

  useEffect(() => {
    if (!activeRun) return;
    setLoadingResults(true);
    api
      .getEvaluationResults(activeRun.id)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setLoadingResults(false));
  }, [activeRun]);

  const handleRunBenchmark = async () => {
    if (!activeProject || !selectedAgentId) {
      showToast("Select an agent to benchmark", "warning");
      return;
    }
    setRunning(true);
    try {
      const run = await api.runEvaluation(activeProject.id, selectedAgentId, evalMode);
      showToast("21-case security benchmark completed!", "success");
      await loadRuns();
      setActiveRun(run);
    } catch (err: any) {
      showToast(err.message || "Benchmark run failed", "error");
    } finally {
      setRunning(false);
    }
  };

  const protMetrics: BenchmarkMetrics | undefined = activeRun?.metrics?.protected;
  const baseMetrics: BenchmarkMetrics | undefined = activeRun?.metrics?.baseline;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-500" />
            Adversarial Security Benchmarks
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            21-case evaluation suite (18 adversarial, 3 legitimate) measuring empirical ASR, UTER, LTSR, and FBR.
          </p>
        </div>

        {/* Trigger Controls */}
        <div className="flex items-center gap-3">
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
          >
            {agents.map((ag) => (
              <option key={ag.id} value={ag.id}>
                Agent: {ag.name}
              </option>
            ))}
          </select>

          <select
            value={evalMode}
            onChange={(e) => setEvalMode(e.target.value as any)}
            className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
          >
            <option value="both">Mode: Both (Comparative)</option>
            <option value="protected">Mode: Protected Only</option>
            <option value="baseline">Mode: Baseline Only</option>
          </select>

          <button
            onClick={handleRunBenchmark}
            disabled={running || !selectedAgentId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-xs shadow-md shadow-blue-600/20 transition-all shrink-0"
          >
            {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
            Execute Suite
          </button>
        </div>
      </div>

      {/* Comparative Metrics Dashboard */}
      {activeRun && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* ASR Card */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="font-semibold uppercase tracking-wider">Attack Success Rate</span>
                <span className="text-[10px] font-mono">Lower is better</span>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-emerald-400">
                    {protMetrics?.asr !== null && protMetrics?.asr !== undefined
                      ? `${(protMetrics.asr * 100).toFixed(1)}%`
                      : "N/A"}
                  </div>
                  <div className="text-[11px] text-zinc-500">Protected Mode</div>
                </div>
                {baseMetrics?.asr !== undefined && (
                  <div className="text-right">
                    <div className="text-sm font-bold font-mono text-rose-400">
                      {baseMetrics.asr !== null ? `${(baseMetrics.asr * 100).toFixed(1)}%` : "N/A"}
                    </div>
                    <div className="text-[11px] text-zinc-500">Baseline</div>
                  </div>
                )}
              </div>
              <div className="mt-3 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${Math.max(2, (1 - (protMetrics?.asr ?? 0)) * 100)}%` }}
                />
              </div>
            </div>

            {/* UTER Card */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="font-semibold uppercase tracking-wider">Unauth Tool Exec Rate</span>
                <span className="text-[10px] font-mono">Zero Leak Goal</span>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-emerald-400">
                    {protMetrics?.uter !== null && protMetrics?.uter !== undefined
                      ? `${(protMetrics.uter * 100).toFixed(1)}%`
                      : "N/A"}
                  </div>
                  <div className="text-[11px] text-zinc-500">Protected Mode</div>
                </div>
                {baseMetrics?.uter !== undefined && (
                  <div className="text-right">
                    <div className="text-sm font-bold font-mono text-rose-400">
                      {baseMetrics.uter !== null ? `${(baseMetrics.uter * 100).toFixed(1)}%` : "N/A"}
                    </div>
                    <div className="text-[11px] text-zinc-500">Baseline</div>
                  </div>
                )}
              </div>
              <div className="mt-3 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${Math.max(2, (1 - (protMetrics?.uter ?? 0)) * 100)}%` }}
                />
              </div>
            </div>

            {/* LTSR Card */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="font-semibold uppercase tracking-wider">Legitimate Task Success</span>
                <span className="text-[10px] font-mono">Higher is better</span>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-blue-400">
                    {protMetrics?.ltsr !== null && protMetrics?.ltsr !== undefined
                      ? `${(protMetrics.ltsr * 100).toFixed(1)}%`
                      : "N/A"}
                  </div>
                  <div className="text-[11px] text-zinc-500">Protected Mode</div>
                </div>
                {baseMetrics?.ltsr !== undefined && (
                  <div className="text-right">
                    <div className="text-sm font-bold font-mono text-zinc-400">
                      {baseMetrics.ltsr !== null ? `${(baseMetrics.ltsr * 100).toFixed(1)}%` : "N/A"}
                    </div>
                    <div className="text-[11px] text-zinc-500">Baseline</div>
                  </div>
                )}
              </div>
              <div className="mt-3 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500"
                  style={{ width: `${(protMetrics?.ltsr ?? 1) * 100}%` }}
                />
              </div>
            </div>

            {/* Latency Card */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="font-semibold uppercase tracking-wider">Policy Engine Latency</span>
                <span className="text-[10px] font-mono">Pure Python</span>
              </div>
              <div className="mt-3">
                <div className="text-2xl font-bold font-mono text-purple-400">
                  {protMetrics?.policy_latency_p95_ms !== null &&
                  protMetrics?.policy_latency_p95_ms !== undefined
                    ? `${protMetrics.policy_latency_p95_ms.toFixed(2)} ms`
                    : "< 1.0 ms"}
                </div>
                <div className="text-[11px] text-zinc-500 mt-1 flex items-center justify-between">
                  <span>p50: {protMetrics?.policy_latency_p50_ms?.toFixed(2) ?? "0.1"}ms</span>
                  <span>max: {protMetrics?.policy_latency_max_ms?.toFixed(2) ?? "1.0"}ms</span>
                </div>
              </div>
              <div className="mt-3 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div className="h-full bg-purple-500 w-1/3" />
              </div>
            </div>
          </div>

          {/* Detailed 21 Case Results Breakdown Table */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300">
                21-Case Benchmark Case Breakdown ({results.length} Executed)
              </h2>
              <span className="text-xs font-mono text-zinc-500">Run ID: {activeRun.id.slice(0, 8)}...</span>
            </div>

            {loadingResults ? (
              <div className="py-8 text-center text-zinc-500 text-xs">Loading case results...</div>
            ) : results.length === 0 ? (
              <div className="py-6 text-center text-zinc-500 text-xs">No case result records.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-zinc-950 text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                    <tr>
                      <th className="py-2.5 px-3">Case ID</th>
                      <th className="py-2.5 px-3">Outcome</th>
                      <th className="py-2.5 px-3">Attack Intercepted?</th>
                      <th className="py-2.5 px-3">Tool Executed?</th>
                      <th className="py-2.5 px-3">Total Latency</th>
                      <th className="py-2.5 px-3">Policy Latency</th>
                      <th className="py-2.5 px-3">Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {results.map((res) => {
                      const isIntercepted = !res.attack_succeeded && !res.tool_executed;
                      return (
                        <tr key={res.id} className="hover:bg-zinc-950/40">
                          <td className="py-2.5 px-3 text-zinc-200 font-semibold">{res.case_id}</td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-sm text-[10px] font-bold ${
                                res.actual_result === "DENIED"
                                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                  : res.actual_result === "COMPLETED"
                                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                  : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                              }`}
                            >
                              {res.actual_result}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            {isIntercepted ? (
                              <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                                <CheckCircle2 className="w-3.5 h-3.5" /> BLOCKED
                              </span>
                            ) : (
                              <span className="text-zinc-500">N/A</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3">
                            {res.tool_executed ? (
                              <span className="text-amber-400 font-semibold">YES</span>
                            ) : (
                              <span className="text-zinc-500">NO</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-zinc-400">
                            {res.execution_latency_ms.toFixed(1)}ms
                          </td>
                          <td className="py-2.5 px-3 text-purple-400">
                            {res.policy_eval_latency_ms ? `${res.policy_eval_latency_ms.toFixed(2)}ms` : "0.0ms"}
                          </td>
                          <td className="py-2.5 px-3 text-zinc-500 truncate max-w-xs">
                            {res.failure_reason || "Deterministic rule verified"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* History of Evaluation Runs */}
      {evalRuns.length > 1 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300 mb-3 flex items-center gap-2">
            <History className="w-4 h-4" /> Benchmark Run History
          </h2>
          <div className="divide-y divide-zinc-800">
            {evalRuns.map((r) => (
              <div
                key={r.id}
                onClick={() => setActiveRun(r)}
                className={`p-3 flex items-center justify-between text-xs cursor-pointer hover:bg-zinc-950 transition-colors ${
                  activeRun?.id === r.id ? "bg-zinc-950 font-semibold text-blue-400" : "text-zinc-300"
                }`}
              >
                <span>Run: {r.id.slice(0, 8)}... ({r.mode})</span>
                <span className="text-zinc-500 font-mono">{new Date(r.started_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
