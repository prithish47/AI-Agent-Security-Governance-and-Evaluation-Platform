// =============================================================================
// AgentGuard — Projects & Tenancy Management View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { Project, ProjectMember } from "@/types";
import { FolderKanban, Plus, Users, Shield, Check, Trash2, Loader2, X } from "lucide-react";

export default function ProjectsView() {
  const { projects, activeProject, setActiveProject, refreshProjects, showToast } = useApp();
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!activeProject) return;
    setLoadingMembers(true);
    api
      .listMembers(activeProject.id)
      .then(setMembers)
      .catch(() => setMembers([]))
      .finally(() => setLoadingMembers(false));
  }, [activeProject]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const p = await api.createProject({ name, description });
      showToast(`Created workspace: ${p.name}`, "success");
      await refreshProjects();
      setActiveProject(p);
      setCreateModalOpen(false);
      setName("");
      setDescription("");
    } catch (err: any) {
      showToast(err.message || "Failed to create project", "error");
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
            <FolderKanban className="w-5 h-5 text-blue-500" />
            Workspace & Tenant Isolation
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            AgentGuard enforces hard multi-tenant isolation. Agents and tools belong strictly to their assigned workspace.
          </p>
        </div>
        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {projects.map((p) => {
          const isActive = activeProject?.id === p.id;
          return (
            <div
              key={p.id}
              onClick={() => setActiveProject(p)}
              className={`p-5 rounded-xl border transition-all cursor-pointer relative ${
                isActive
                  ? "bg-blue-950/20 border-blue-500/40 shadow-lg shadow-blue-950/30 ring-1 ring-blue-500/30"
                  : "bg-zinc-900 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/80"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-zinc-200 truncate">{p.name}</span>
                {isActive && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
                    <Check className="w-3 h-3" /> Active
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 line-clamp-2 min-h-8">
                {p.description || "No description provided."}
              </p>
              <div className="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] font-mono text-zinc-500">
                <span>ID: {p.id.slice(0, 8)}...</span>
                <span>{new Date(p.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Workspace Details & Members */}
      {activeProject && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-blue-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-300">
                Authorized Members & RBAC Roles ({activeProject.name})
              </h2>
            </div>
          </div>

          {loadingMembers ? (
            <div className="py-8 flex justify-center text-zinc-500 text-xs">Loading membership...</div>
          ) : members.length === 0 ? (
            <div className="py-6 text-center text-xs text-zinc-500">
              No additional project members listed. Platform administrators hold sovereign access.
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/60 border border-zinc-800/80 rounded-lg overflow-hidden">
              {members.map((m) => (
                <div key={m.id} className="p-3.5 bg-zinc-950 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-zinc-300">{m.user_id.slice(0, 12)}...</span>
                    <span
                      className={`px-2 py-0.5 rounded-md font-semibold text-[10px] ${
                        m.role === "OWNER"
                          ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                          : m.role === "ADMIN"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          : m.role === "APPROVER"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                      }`}
                    >
                      {m.role}
                    </span>
                  </div>
                  <span className="text-zinc-500 text-[11px]">
                    Joined {new Date(m.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create Project Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
            <button
              onClick={() => setCreateModalOpen(false)}
              className="absolute top-4 right-4 p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800"
            >
              <X className="w-5 h-5" />
            </button>
            <h2 className="text-base font-bold text-zinc-100 mb-1">Create Workspace Project</h2>
            <p className="text-xs text-zinc-400 mb-4">
              Workspaces isolate all policies, agents, tools, audit events, and benchmark evaluations.
            </p>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">Project Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Customer Support Agent Workspace"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">Description (Optional)</label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Production financial and customer support agent environment..."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
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
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
