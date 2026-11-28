// =============================================================================
// AgentGuard — Main Dashboard Page
// =============================================================================

"use client";

import React, { useState } from "react";
import { AppProvider, useApp } from "@/context/AppContext";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import AuthModal from "@/components/AuthModal";
import { Loader2, Shield } from "lucide-react";

// Views
import OverviewView from "@/components/views/OverviewView";
import ProjectsView from "@/components/views/ProjectsView";
import AgentsView from "@/components/views/AgentsView";
import ToolsView from "@/components/views/ToolsView";
import PoliciesView from "@/components/views/PoliciesView";
import PlaygroundView from "@/components/views/PlaygroundView";
import ApprovalsView from "@/components/views/ApprovalsView";
import EvaluationsView from "@/components/views/EvaluationsView";
import AuditLogsView from "@/components/views/AuditLogsView";
import SettingsView from "@/components/views/SettingsView";

function DashboardContent() {
  const { user, authLoading, activeView } = useApp();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  if (authLoading) {
    return (
      <div className="flex h-screen bg-zinc-950 text-zinc-100 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Shield className="w-6 h-6" />
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
            <span>Verifying session...</span>
          </div>
        </div>
      </div>
    );
  }

  // When unauthenticated, do not mount protected dashboard views or trigger project API requests
  if (!user) {
    return (
      <div className="flex h-screen bg-zinc-950 text-zinc-100 items-center justify-center">
        <AuthModal isOpen={true} requireAuth={true} onClose={() => setAuthModalOpen(false)} />
      </div>
    );
  }

  const renderActiveView = () => {
    switch (activeView) {
      case "overview":
        return <OverviewView />;
      case "projects":
        return <ProjectsView />;
      case "agents":
        return <AgentsView />;
      case "tools":
        return <ToolsView />;
      case "policies":
        return <PoliciesView />;
      case "playground":
        return <PlaygroundView />;
      case "approvals":
        return <ApprovalsView />;
      case "evaluations":
        return <EvaluationsView />;
      case "audit":
        return <AuditLogsView />;
      case "settings":
        return <SettingsView />;
      default:
        return <OverviewView />;
    }
  };

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 overflow-hidden font-sans antialiased">
      {/* Fixed Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navigation */}
        <TopNav onOpenAuth={() => setAuthModalOpen(true)} />

        {/* Scrollable View Container */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto">{renderActiveView()}</div>
        </main>
      </div>

      {/* Auth Modal */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </div>
  );
}

export default function Home() {
  return (
    <AppProvider>
      <DashboardContent />
    </AppProvider>
  );
}
