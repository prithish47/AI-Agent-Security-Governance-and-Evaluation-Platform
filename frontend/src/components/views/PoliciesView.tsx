// =============================================================================
// AgentGuard — Security Policies View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { SecurityPolicy, PolicyVersion } from "@/types";
import { ShieldCheck, Plus, History, CheckCircle2, Code, Loader2, X, AlertCircle } from "lucide-react";

export default function PoliciesView() {
  const { activeProject, showToast } = useApp();
  const [policies, setPolicies] = useState<SecurityPolicy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<SecurityPolicy | null>(null);
  const [versions, setVersions] = useState<PolicyVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingVersions, setLoadingVersions] = useState(false);

  // Create Policy Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [policyName, setPolicyName] = useState("");
  const [policyDesc, setPolicyDesc] = useState("");

  // Create Version Modal
  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [rulesJson, setRulesJson] = useState(
    JSON.stringify(
      {
        allowed_tools: ["lookupCustomer", "queryKnowledgeBase", "processRefund"],
        explicit_denies: ["deleteDatabase", "exportAllCustomers", "unrestrictedShell"],
        max_risk_level: "HIGH",
        requires_approval: ["processRefund"],
        argument_constraints: {
          processRefund: {
            amount: { max: 500, min: 1 },
          },
        },
        argument_patterns: {
          sql_injection: "(?i)(union\\s+select|drop\\s+table|delete\\s+from)",
          path_traversal: "\\.\\./|\\.\\.\\\\",
        },
      },
      null,
      2
    )
  );
  const [submitting, setSubmitting] = useState(false);

  const loadPolicies = async () => {
    if (!activeProject) return;
    setLoading(true);
    try {
      const data = await api.listPolicies(activeProject.id);
      setPolicies(data);
      if (data.length > 0 && !selectedPolicy) {
        setSelectedPolicy(data[0]);
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicies();
  }, [activeProject]);

  useEffect(() => {
    if (!selectedPolicy) return;
    setLoadingVersions(true);
    api
      .listPolicyVersions(selectedPolicy.id)
      .then(setVersions)
      .catch(() => setVersions([]))
      .finally(() => setLoadingVersions(false));
  }, [selectedPolicy]);

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    setSubmitting(true);
    try {
      let parsedRules: Record<string, any>;
      try {
        parsedRules = JSON.parse(rulesJson);
      } catch {
        showToast("Invalid JSON rules schema syntax", "error");
        setSubmitting(false);
        return;
      }

      const p = await api.createPolicy(activeProject.id, {
        name: policyName,
        description: policyDesc,
        rules: parsedRules,
      });

      showToast(`Created security policy: ${p.name}`, "success");
      setCreateModalOpen(false);
      setPolicyName("");
      setPolicyDesc("");
      await loadPolicies();
      setSelectedPolicy(p);
    } catch (err: any) {
      showToast(err.message || "Failed to create policy", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPolicy) return;
    setSubmitting(true);
    try {
      const parsed = JSON.parse(rulesJson);
      const v = await api.createPolicyVersion(selectedPolicy.id, parsed);
      showToast(`Created Policy Version v${v.version_number}`, "success");
      setVersionModalOpen(false);
      const updatedVersions = await api.listPolicyVersions(selectedPolicy.id);
      setVersions(updatedVersions);
    } catch (err: any) {
      showToast(err.message || "Failed to create version", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleActivateVersion = async (versionId: string) => {
    if (!selectedPolicy) return;
    try {
      await api.activatePolicyVersion(selectedPolicy.id, versionId);
      showToast("Policy version activated", "success");
      const updatedVersions = await api.listPolicyVersions(selectedPolicy.id);
      setVersions(updatedVersions);
      await loadPolicies();
    } catch (err: any) {
      showToast(err.message || "Failed to activate version", "error");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-purple-400" />
            Security Policy & Rule Engine
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Deterministic 7-rule evaluation order with fail-closed default and immutable versioning.
          </p>
        </div>
        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Policy
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left: Policy Selector */}
        <div className="space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Policies</div>
          {loading ? (
            <div className="py-8 text-center text-zinc-500 text-xs">Loading policies...</div>
          ) : policies.length === 0 ? (
            <div className="p-6 bg-zinc-900 border border-dashed border-zinc-800 rounded-xl text-center text-xs text-zinc-500">
              No policies created yet.
            </div>
          ) : (
            policies.map((p) => {
              const isSelected = selectedPolicy?.id === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedPolicy(p)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? "bg-purple-950/20 border-purple-500/40 ring-1 ring-purple-500/30"
                      : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-zinc-200 text-sm">{p.name}</span>
                    {isSelected && (
                      <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full border border-purple-500/20">
                        Selected
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400 line-clamp-2">{p.description || "Deterministic rule set."}</p>
                </div>
              );
            })
          )}
        </div>

        {/* Right: Policy Versions & Rules */}
        <div className="md:col-span-2 space-y-4">
          {selectedPolicy ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-base font-bold text-zinc-100">{selectedPolicy.name}</h2>
                  <p className="text-xs text-zinc-400">{selectedPolicy.description}</p>
                </div>
                <button
                  onClick={() => setVersionModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  New Version
                </button>
              </div>

              <div className="space-y-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                  <History className="w-3.5 h-3.5" />
                  Version History & Rules
                </div>

                {loadingVersions ? (
                  <div className="py-6 text-center text-zinc-500 text-xs">Loading versions...</div>
                ) : versions.length === 0 ? (
                  <div className="p-4 bg-zinc-950 rounded-lg text-center text-xs text-zinc-500">
                    No versions found.
                  </div>
                ) : (
                  versions.map((v) => (
                    <div
                      key={v.id}
                      className={`p-4 rounded-xl border ${
                        v.is_active
                          ? "bg-zinc-950 border-emerald-500/30"
                          : "bg-zinc-950/60 border-zinc-800"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-sm text-zinc-200">
                            Version {v.version_number}
                          </span>
                          {v.is_active ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                              <CheckCircle2 className="w-3 h-3" /> ACTIVE
                            </span>
                          ) : (
                            <button
                              onClick={() => handleActivateVersion(v.id)}
                              className="text-[11px] font-medium text-blue-400 hover:text-blue-300 underline underline-offset-2"
                            >
                              Activate this version
                            </button>
                          )}
                        </div>
                        <span className="text-[11px] font-mono text-zinc-500">
                          {new Date(v.created_at).toLocaleString()}
                        </span>
                      </div>

                      <pre className="bg-zinc-900 p-3 rounded-lg border border-zinc-800 text-[11px] font-mono text-zinc-300 overflow-x-auto max-h-48 mt-2">
                        {JSON.stringify(v.rules, null, 2)}
                      </pre>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center bg-zinc-900 border border-zinc-800 rounded-xl text-xs text-zinc-500">
              Select a security policy to view versions and rules.
            </div>
          )}
        </div>
      </div>

      {/* Create Policy Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setCreateModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 mb-1">Create Security Policy</h2>
            <p className="text-xs text-zinc-400 mb-4">
              Instantiate a deterministic policy container with version 1 rules.
            </p>

            <form onSubmit={handleCreatePolicy} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Policy Name</label>
                <input
                  type="text"
                  required
                  value={policyName}
                  onChange={(e) => setPolicyName(e.target.value)}
                  placeholder="Production Customer Support Policy"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Description</label>
                <input
                  type="text"
                  value={policyDesc}
                  onChange={(e) => setPolicyDesc(e.target.value)}
                  placeholder="Enforces bounds on refund tools and restricts SQL injection patterns"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Version 1 Rules (JSON)</label>
                <textarea
                  rows={8}
                  value={rulesJson}
                  onChange={(e) => setRulesJson(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
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
                  Create Policy
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Version Modal */}
      {versionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setVersionModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 mb-1">Create New Policy Version</h2>
            <p className="text-xs text-zinc-400 mb-4">
              Add an immutable version snapshot to {selectedPolicy?.name}.
            </p>

            <form onSubmit={handleCreateVersion} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">Rules Specification (JSON)</label>
                <textarea
                  rows={10}
                  value={rulesJson}
                  onChange={(e) => setRulesJson(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={() => setVersionModalOpen(false)}
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
                  Save Version
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
