// =============================================================================
// AgentGuard — Agents Management View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { Agent, ToolDefinition, SecurityPolicy, RiskLevel } from "@/types";
import {
  Bot,
  Plus,
  Shield,
  Wrench,
  Lock,
  Loader2,
  X,
  CheckCircle2,
  AlertTriangle,
  Play,
} from "lucide-react";

export default function AgentsView() {
  const { activeProject, setActiveView, showToast } = useApp();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
  const [loading, setLoading] = useState(true);

  // Create Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(
    "You are a helpful customer support agent. Help users solve issues using your authorized tools."
  );
  const [modelProvider, setModelProvider] = useState("mock");
  const [modelName, setModelName] = useState("mock-gpt-4");
  const [maxIterations, setMaxIterations] = useState(10);
  const [maxRiskLevel, setMaxRiskLevel] = useState<RiskLevel>("HIGH");
  const [policyId, setPolicyId] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  // Tool Assignment Modal State
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const loadData = async () => {
    if (!activeProject) return;
    setLoading(true);
    try {
      const [ag, tl, pol] = await Promise.all([
        api.listAgents(activeProject.id),
        api.listTools(activeProject.id),
        api.listPolicies(activeProject.id),
      ]);
      setAgents(ag);
      setTools(tl);
      setPolicies(pol);
      if (pol.length > 0 && !policyId) {
        setPolicyId(pol[0].id);
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeProject]);

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    setSubmitting(true);
    try {
      await api.createAgent(activeProject.id, {
        name,
        description,
        system_prompt: systemPrompt,
        model_provider: modelProvider,
        model_name: modelName,
        max_iterations: Number(maxIterations),
        max_risk_level: maxRiskLevel,
        policy_id: policyId || undefined,
        is_enabled: true,
      });
      showToast(`Registered agent: ${name}`, "success");
      setModalOpen(false);
      setName("");
      setDescription("");
      await loadData();
    } catch (err: any) {
      showToast(err.message || "Failed to register agent", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleTool = async (agent: Agent, toolId: string, isAssigned: boolean) => {
    try {
      if (isAssigned) {
        await api.unassignTool(agent.id, toolId);
        showToast("Tool unassigned", "info");
      } else {
        await api.assignTool(agent.id, toolId);
        showToast("Tool assigned", "success");
      }
      await loadData();
    } catch (err: any) {
      showToast(err.message || "Failed to modify tool assignment", "error");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Bot className="w-5 h-5 text-blue-500" />
            AI Agents Registry
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Agents have strict risk level ceilings, pinned policy associations, and bounded iteration limits.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          Register Agent
        </button>
      </div>

      {/* Agents List */}
      {loading ? (
        <div className="py-12 flex justify-center text-zinc-500 text-xs">Loading registered agents...</div>
      ) : agents.length === 0 ? (
        <div className="p-12 text-center bg-zinc-900 border border-dashed border-zinc-800 rounded-xl">
          <Bot className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-zinc-300">No agents registered</h3>
          <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
            Create an agent to test prompts, enforce policy ceilings, and execute governed tools.
          </p>
          <button
            onClick={() => setModalOpen(true)}
            className="mt-4 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
          >
            Register First Agent
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {agents.map((ag) => (
            <div
              key={ag.id}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between hover:border-zinc-700 transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-zinc-200 text-sm">{ag.name}</span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                      ag.max_risk_level === "CRITICAL"
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : ag.max_risk_level === "HIGH"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : ag.max_risk_level === "MEDIUM"
                        ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                        : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    }`}
                  >
                    Ceiling: {ag.max_risk_level}
                  </span>
                </div>

                <p className="text-xs text-zinc-400 line-clamp-2 min-h-8 mb-3">
                  {ag.description || "Governed AI agent instance."}
                </p>

                <div className="space-y-1.5 text-xs text-zinc-500 bg-zinc-950/70 p-3 rounded-lg border border-zinc-800/80 font-mono">
                  <div className="flex justify-between">
                    <span>Provider:</span>
                    <span className="text-zinc-300">{ag.model_provider} ({ag.model_name})</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Iteration Ceiling:</span>
                    <span className="text-zinc-300">{ag.max_iterations} turns max</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Status:</span>
                    <span className={ag.is_enabled ? "text-emerald-400" : "text-zinc-500"}>
                      {ag.is_enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center justify-between gap-2">
                <button
                  onClick={() => {
                    setSelectedAgent(ag);
                    setAssignModalOpen(true);
                  }}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Wrench className="w-3.5 h-3.5 text-emerald-400" />
                  Tool Matrix
                </button>
                <button
                  onClick={() => setActiveView("playground")}
                  className="py-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium flex items-center gap-1.5 shadow-sm transition-colors"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  Run
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tool Matrix Modal */}
      {assignModalOpen && selectedAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <button
              onClick={() => setAssignModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 mb-1">
              Tool Permissions Matrix: {selectedAgent.name}
            </h2>
            <p className="text-xs text-zinc-400 mb-4">
              Rule 1 (Tool Permission) explicitly denies any tool not assigned here.
            </p>

            <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
              {tools.map((t) => (
                <div
                  key={t.id}
                  className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 flex items-center justify-between"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-zinc-200">{t.name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm bg-zinc-800 text-zinc-400">
                        {t.risk_level}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-500 mt-0.5 truncate max-w-xs">{t.description}</p>
                  </div>

                  <button
                    onClick={() => handleToggleTool(selectedAgent, t.id, false)}
                    className="px-3 py-1 rounded-md text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white"
                  >
                    Assign
                  </button>
                </div>
              ))}
            </div>

            <div className="mt-4 pt-3 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setAssignModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Agent Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 mb-1">Register New AI Agent</h2>
            <p className="text-xs text-zinc-400 mb-4">
              Configure risk level ceiling, iteration bounds, and model connection.
            </p>

            <form onSubmit={handleCreateAgent} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Agent Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Billing Support Agent"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Description</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Handles refunds and customer support inquiries"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Model Provider</label>
                  <select
                    value={modelProvider}
                    onChange={(e) => setModelProvider(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                  >
                    <option value="mock">Deterministic Mock</option>
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Google Gemini</option>
                    <option value="ollama">Ollama (Local)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Model Name</label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    placeholder="gpt-4o / gemini-1.5-pro"
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Max Risk Ceiling</label>
                  <select
                    value={maxRiskLevel}
                    onChange={(e) => setMaxRiskLevel(e.target.value as RiskLevel)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Max Iterations</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={maxIterations}
                    onChange={(e) => setMaxIterations(Number(e.target.value))}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Active Security Policy</label>
                <select
                  value={policyId}
                  onChange={(e) => setPolicyId(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                >
                  <option value="">Default Policy</option>
                  {policies.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">System Prompt</label>
                <textarea
                  rows={3}
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white flex items-center gap-2"
                >
                  {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Register Agent
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
