// =============================================================================
// AgentGuard — Sidebar Navigation
// =============================================================================

"use client";

import React from "react";
import { useApp } from "@/context/AppContext";
import {
  LayoutDashboard,
  FolderKanban,
  Bot,
  Wrench,
  ShieldCheck,
  Terminal,
  ClockAlert,
  BarChart3,
  ScrollText,
  Settings,
  Shield,
} from "lucide-react";

export default function Sidebar() {
  const { activeView, setActiveView, pendingApprovalsCount } = useApp();

  const navItems = [
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "projects", label: "Projects", icon: FolderKanban },
    { id: "agents", label: "Agents", icon: Bot },
    { id: "tools", label: "Tool Catalog", icon: Wrench },
    { id: "policies", label: "Security Policies", icon: ShieldCheck },
    { id: "playground", label: "Playground", icon: Terminal },
    {
      id: "approvals",
      label: "Approvals",
      icon: ClockAlert,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
    },
    { id: "evaluations", label: "Evaluations", icon: BarChart3 },
    { id: "audit", label: "Audit Logs", icon: ScrollText },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  return (
    <aside className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col shrink-0 select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-zinc-800">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <div className="font-semibold text-zinc-100 tracking-tight leading-none text-base">AgentGuard</div>
          <div className="text-[11px] text-zinc-400 font-mono tracking-wider mt-1 uppercase">Security Platform</div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
          Platform Governance
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 ${isActive ? "text-blue-400" : "text-zinc-400"}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span className="px-2 py-0.5 text-xs font-mono font-bold bg-amber-500 text-zinc-950 rounded-full animate-pulse">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Status */}
      <div className="p-4 border-t border-zinc-800 text-xs text-zinc-400 font-mono flex items-center justify-between">
        <span>Boundary Status</span>
        <span className="inline-flex items-center gap-1.5 text-emerald-400 font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          ACTIVE
        </span>
      </div>
    </aside>
  );
}
