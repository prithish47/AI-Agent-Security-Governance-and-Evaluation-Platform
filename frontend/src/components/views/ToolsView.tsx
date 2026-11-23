// =============================================================================
// AgentGuard — Tool Catalog View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { ToolDefinition, RiskLevel } from "@/types";
import { Wrench, Plus, ShieldCheck, Code, AlertTriangle, X, Loader2 } from "lucide-react";

export default function ToolsView() {
  const { activeProject, showToast } = useApp();
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedTool, setSelectedTool] = useState<ToolDefinition | null>(null);

  // Form
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [riskLevel, setRiskLevel] = useState<RiskLevel>("LOW");
  const [schemaStr, setSchemaStr] = useState(
    JSON.stringify(
      {
        type: "object",
        properties: {
          customer_id: { type: "string" },
        },
        required: ["customer_id"],
      },
      null,
      2
    )
  );
  const [submitting, setSubmitting] = useState(false);

  const loadTools = async () => {
    if (!activeProject) return;
    setLoading(true);
    try {
      const data = await api.listTools(activeProject.id);
      setTools(data);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTools();
  }, [activeProject]);

  const handleCreateTool = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    setSubmitting(true);
    try {
      let parsedSchema: Record<string, any>;
      try {
        parsedSchema = JSON.parse(schemaStr);
      } catch {
        showToast("Invalid JSON schema syntax", "error");
        setSubmitting(false);
        return;
      }

      await api.createTool(activeProject.id, {
        name,
        description,
        input_schema: parsedSchema,
        risk_level: riskLevel,
        is_enabled: true,
      });

      showToast(`Registered tool: ${name}`, "success");
      setModalOpen(false);
      setName("");
      setDescription("");
      await loadTools();
    } catch (err: any) {
      showToast(err.message || "Failed to register tool", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Wrench className="w-5 h-5 text-emerald-500" />
            Guarded Tool Catalog
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Database records define tool interfaces. Executables are bound strictly to the precompiled Python whitelist.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          Register Tool
        </button>
      </div>

      {/* Security Whitelist Notice */}
      <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div className="text-xs text-zinc-400">
          <strong className="text-zinc-200">Whitelist Enforcement Guarantee:</strong> Tools cannot execute arbitrary shell or dynamically loaded code. Only functions precompiled into the backend tool registry are executable by AgentGuard.
        </div>
      </div>

      {/* Tools Table / Grid */}
      {loading ? (
        <div className="py-12 flex justify-center text-zinc-500 text-xs">Loading tool definitions...</div>
      ) : tools.length === 0 ? (
        <div className="p-12 text-center bg-zinc-900 border border-dashed border-zinc-800 rounded-xl text-zinc-500 text-xs">
          No tools defined for this workspace.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {tools.map((t) => (
            <div
              key={t.id}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between hover:border-zinc-700 transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-zinc-200 text-sm font-mono">{t.name}</span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                      t.risk_level === "CRITICAL"
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                        : t.risk_level === "HIGH"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : t.risk_level === "MEDIUM"
                        ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                        : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    }`}
                  >
                    {t.risk_level}
                  </span>
                </div>

                <p className="text-xs text-zinc-400 line-clamp-2 min-h-8 mb-3">{t.description}</p>

                <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800 font-mono text-[11px] text-zinc-400">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-zinc-500">Executable Whitelist:</span>
                    <span className={t.is_executable ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
                      {t.is_executable ? "Bound" : "Unbound"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-zinc-500">Status:</span>
                    <span className={t.is_enabled ? "text-emerald-400" : "text-zinc-500"}>
                      {t.is_enabled ? "Active" : "Disabled"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800 flex justify-end">
                <button
                  onClick={() => setSelectedTool(t)}
                  className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
                >
                  <Code className="w-3.5 h-3.5 text-blue-400" />
                  View Schema
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Schema Inspection Modal */}
      {selectedTool && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <button
              onClick={() => setSelectedTool(null)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 font-mono mb-1">{selectedTool.name}</h2>
            <p className="text-xs text-zinc-400 mb-3">{selectedTool.description}</p>

            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
              Input JSON Schema
            </div>
            <pre className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 text-xs font-mono text-zinc-300 overflow-x-auto max-h-72">
              {JSON.stringify(selectedTool.input_schema, null, 2)}
            </pre>

            <div className="mt-4 pt-3 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setSelectedTool(null)}
                className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Tool Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <button
              onClick={() => setModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 mb-1">Register Guarded Tool</h2>
            <p className="text-xs text-zinc-400 mb-4">
              Add a tool definition to the workspace schema catalog.
            </p>

            <form onSubmit={handleCreateTool} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Tool Name (Identifier)</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="lookupCustomer"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Description</label>
                <input
                  type="text"
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Fetch customer profile by unique ID"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Risk Level</label>
                <select
                  value={riskLevel}
                  onChange={(e) => setRiskLevel(e.target.value as RiskLevel)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Input Schema (JSON)</label>
                <textarea
                  rows={6}
                  value={schemaStr}
                  onChange={(e) => setSchemaStr(e.target.value)}
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
                  Register Tool
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
