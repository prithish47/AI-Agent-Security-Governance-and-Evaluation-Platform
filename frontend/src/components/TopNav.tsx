// =============================================================================
// AgentGuard — Top Navigation Bar
// =============================================================================

"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import {
  FolderKanban,
  ClockAlert,
  User as UserIcon,
  LogOut,
  LogIn,
  ChevronDown,
  Plus,
} from "lucide-react";

export default function TopNav({ onOpenAuth }: { onOpenAuth: () => void }) {
  const {
    user,
    projects,
    activeProject,
    setActiveProject,
    pendingApprovalsCount,
    setActiveView,
    logoutUser,
  } = useApp();

  const [projectDropdown, setProjectDropdown] = useState(false);

  return (
    <header className="h-16 bg-zinc-950 border-b border-zinc-800 flex items-center justify-between px-6 shrink-0">
      {/* Current Project Selector */}
      <div className="relative">
        <button
          onClick={() => setProjectDropdown(!projectDropdown)}
          className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:border-zinc-700 text-sm font-medium text-zinc-200 transition-colors"
        >
          <FolderKanban className="w-4 h-4 text-zinc-400" />
          <span>{activeProject ? activeProject.name : "Select Project"}</span>
          <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
        </button>

        {projectDropdown && (
          <div className="absolute top-12 left-0 w-64 bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl py-1 z-50">
            <div className="px-3 py-1.5 text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
              Workspace Tenancy
            </div>
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setActiveProject(p);
                  setProjectDropdown(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between hover:bg-zinc-800 transition-colors ${
                  activeProject?.id === p.id ? "text-blue-400 font-semibold" : "text-zinc-300"
                }`}
              >
                <span className="truncate">{p.name}</span>
                {activeProject?.id === p.id && <span className="text-xs text-blue-400">Active</span>}
              </button>
            ))}
            <div className="border-t border-zinc-800 mt-1 pt-1">
              <button
                onClick={() => {
                  setProjectDropdown(false);
                  setActiveView("projects");
                }}
                className="w-full text-left px-3 py-1.5 text-xs text-blue-400 hover:bg-zinc-800 flex items-center gap-1.5"
              >
                <Plus className="w-3 h-3" /> Manage Projects
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Pending Approvals Indicator */}
        {pendingApprovalsCount > 0 && (
          <button
            onClick={() => setActiveView("approvals")}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-xs font-medium transition-colors"
          >
            <ClockAlert className="w-3.5 h-3.5" />
            <span>{pendingApprovalsCount} Approval{pendingApprovalsCount > 1 ? "s" : ""} Pending</span>
          </button>
        )}

        {/* User Account / Auth */}
        {user ? (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-mono text-zinc-300">
              <UserIcon className="w-3.5 h-3.5 text-zinc-400" />
              <span>{user.username}</span>
            </div>
            <button
              onClick={() => logoutUser()}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-zinc-900 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition-all"
          >
            <LogIn className="w-3.5 h-3.5" />
            Sign In
          </button>
        )}
      </div>
    </header>
  );
}
