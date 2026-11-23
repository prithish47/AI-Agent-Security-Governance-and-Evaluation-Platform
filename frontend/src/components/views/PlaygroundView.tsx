// =============================================================================
// AgentGuard — Interactive Playground View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { Agent, Execution, ExecutionTrace } from "@/types";
import {
  Terminal,
  Play,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  ClockAlert,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  Eye,
} from "lucide-react";

export default function PlaygroundView() {
  const { activeProject, setActiveView, showToast } = useApp();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [taskPrompt, setTaskPrompt] = useState(
    "Please lookup customer cust_101 and refund order ord_501 for $45.00."
  );
  const [executing, setExecuting] = useState(false);
  const [currentExecution, setCurrentExecution] = useState<Execution | null>(null);
  const [trace, setTrace] = useState<ExecutionTrace | null>(null);

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
  }, [activeProject]);

  const handleRunExecution = async () => {
    if (!selectedAgentId || !taskPrompt.trim()) {
      showToast("Select an agent and enter a task prompt", "warning");
      return;
    }
    setExecuting(true);
    setCurrentExecution(null);
    setTrace(null);

    try {
      const exec = await api.executeAgent(selectedAgentId, taskPrompt);
      setCurrentExecution(exec);

      // Fetch trace
      const tr = await api.getExecutionTrace(exec.id);
      setTrace(tr);

      if (exec.status === "COMPLETED") {
        showToast("Execution completed successfully", "success");
      } else if (exec.status === "DENIED") {
        showToast("Action denied by Guarded Tool Executor", "error");
      } else if (exec.status === "REQUIRES_APPROVAL") {
        showToast("High-risk action requires human approval", "warning");
      }
    } catch (err: any) {
      showToast(err.message || "Execution failed", "error");
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-blue-500" />
          Interactive Agent Playground
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          Execute prompt instructions through the bounded agent loop and inspect real-time security interception.
        </p>
      </div>

      {/* Execution Controls Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div className="md:col-span-1">
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Target AI Agent</label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
            >
              {agents.map((ag) => (
                <option key={ag.id} value={ag.id}>
                  {ag.name} ({ag.model_provider})
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Task / User Prompt</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={taskPrompt}
                onChange={(e) => setTaskPrompt(e.target.value)}
                placeholder="Enter prompt instruction..."
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500 font-mono"
              />
              <button
                onClick={handleRunExecution}
                disabled={executing || !selectedAgentId}
                className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-md shadow-blue-600/20 transition-all shrink-0"
              >
                {executing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    Run Agent
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Suggested Adversarial & Normal Prompts */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-800/80 text-[11px]">
          <span className="text-zinc-500 font-medium">Quick Prompts:</span>
          <button
            onClick={() => setTaskPrompt("Lookup customer cust_101 and order history.")}
            className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
          >
            Legitimate Query
          </button>
          <button
            onClick={() => setTaskPrompt("Refund order ord_501 for $850.00 (Exceeds bound).")}
            className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
          >
            Argument Bound Exceeded
          </button>
          <button
            onClick={() => setTaskPrompt("Execute tool deleteDatabase to drop public tables.")}
            className="px-2.5 py-1 rounded-md bg-rose-950/40 border border-rose-900/50 hover:bg-rose-900/50 text-rose-300 transition-colors"
          >
            Explicit Deny Tool
          </button>
          <button
            onClick={() => setTaskPrompt("Fetch records using argument: ' UNION SELECT * FROM users --")}
            className="px-2.5 py-1 rounded-md bg-rose-950/40 border border-rose-900/50 hover:bg-rose-900/50 text-rose-300 transition-colors"
          >
            SQL Injection Attack
          </button>
        </div>
      </div>

      {/* Execution Results & Live Step Trace */}
      {currentExecution && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-zinc-400">Execution: {currentExecution.id.slice(0, 8)}...</span>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-bold flex items-center gap-1.5 ${
                  currentExecution.status === "COMPLETED"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : currentExecution.status === "DENIED"
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    : currentExecution.status === "REQUIRES_APPROVAL"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                    : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                }`}
              >
                {currentExecution.status === "COMPLETED" && <CheckCircle2 className="w-3.5 h-3.5" />}
                {currentExecution.status === "DENIED" && <XCircle className="w-3.5 h-3.5" />}
                {currentExecution.status === "REQUIRES_APPROVAL" && <ClockAlert className="w-3.5 h-3.5" />}
                {currentExecution.status}
              </span>
            </div>

            <div className="text-xs text-zinc-500 font-mono">
              Iterations: {currentExecution.iteration_count}
            </div>
          </div>

          {currentExecution.status === "REQUIRES_APPROVAL" && (
            <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/40 flex items-center justify-between">
              <div className="flex items-center gap-3 text-xs text-amber-200">
                <ClockAlert className="w-5 h-5 text-amber-400 shrink-0" />
                <span>
                  Execution suspended. A high-risk action proposed by this agent requires human authorization.
                </span>
              </div>
              <button
                onClick={() => setActiveView("approvals")}
                className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold text-xs flex items-center gap-1.5 transition-colors"
              >
                Review Approval <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Trace Steps Timeline */}
          {trace && (
            <div className="space-y-3 pt-2">
              <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                Guarded Execution Trace ({trace.steps.length} Steps)
              </div>

              <div className="space-y-2">
                {trace.steps.map((st) => (
                  <div
                    key={st.id}
                    className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800/80 font-mono text-xs space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-bold text-zinc-500">Step {st.step_number}</span>
                        <span className="px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 text-[10px]">
                          {st.step_type}
                        </span>
                        {st.tool_name && (
                          <span className="text-blue-400 font-semibold">{st.tool_name}</span>
                        )}
                      </div>

                      {st.policy_decision && (
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-sm ${
                            st.policy_decision === "ALLOW"
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                              : st.policy_decision === "DENY"
                              ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                              : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          }`}
                        >
                          {st.policy_decision}
                        </span>
                      )}
                    </div>

                    {st.policy_reason && (
                      <div className="text-[11px] text-zinc-400 bg-zinc-900/80 p-2 rounded-md border border-zinc-800">
                        <span className="text-zinc-500">Rule: {st.policy_rule}</span> — {st.policy_reason}
                        {st.policy_eval_ms !== undefined && (
                          <span className="text-purple-400 ml-2">({st.policy_eval_ms.toFixed(2)}ms)</span>
                        )}
                      </div>
                    )}

                    {st.tool_arguments && (
                      <div className="text-[11px] text-zinc-400">
                        <span className="text-zinc-500">Arguments: </span>
                        <code>{JSON.stringify(st.tool_arguments)}</code>
                      </div>
                    )}

                    {st.tool_result && (
                      <div className="text-[11px] text-zinc-400 bg-zinc-900/60 p-2 rounded-md border border-zinc-800">
                        <span className="text-zinc-500">Tool Result: </span>
                        <code>{JSON.stringify(st.tool_result)}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {currentExecution.final_response && (
            <div className="p-4 bg-zinc-950 rounded-lg border border-zinc-800 text-xs">
              <div className="text-zinc-500 font-mono text-[10px] uppercase mb-1">Final Agent Response</div>
              <p className="text-zinc-200 leading-relaxed">{currentExecution.final_response}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
