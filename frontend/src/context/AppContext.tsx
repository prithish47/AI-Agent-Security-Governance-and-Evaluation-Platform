// =============================================================================
// AgentGuard — Application State & Authentication Context
// =============================================================================

"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import api, {
  clearSessionTokens,
  getAccessToken,
  getRefreshToken,
  hasRefreshToken,
  setAuthFailureHandler,
  setSessionTokens,
} from "@/lib/api-client";
import { Project, User } from "@/types";

interface ToastNotification {
  id: string;
  type: "success" | "error" | "info" | "warning";
  message: string;
}

interface AppContextType {
  user: User | null;
  authLoading: boolean;
  projects: Project[];
  activeProject: Project | null;
  pendingApprovalsCount: number;
  activeView: string;
  setActiveView: (view: string) => void;
  setActiveProject: (project: Project | null) => void;
  loginUser: (email: string, password: string) => Promise<void>;
  registerUser: (email: string, username: string, password: string) => Promise<void>;
  logoutUser: () => Promise<void>;
  refreshProjects: () => Promise<void>;
  refreshPendingApprovals: () => Promise<void>;
  showToast: (message: string, type?: "success" | "error" | "info" | "warning") => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);
  const [activeView, setActiveView] = useState<string>("overview");
  const [toasts, setToasts] = useState<ToastNotification[]>([]);

  const showToast = useCallback(
    (message: string, type: "success" | "error" | "info" | "warning" = "info") => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, type, message }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    },
    []
  );

  const clearAuthState = useCallback(() => {
    clearSessionTokens();
    setUser(null);
    setProjects([]);
    setActiveProject(null);
    setPendingApprovalsCount(0);
    setActiveView("overview");
  }, []);

  const refreshPendingApprovals = useCallback(async () => {
    if (!user || !activeProject) {
      setPendingApprovalsCount(0);
      return;
    }
    try {
      const approvals = await api.listApprovals(activeProject.id, "PENDING");
      setPendingApprovalsCount(approvals.length);
    } catch {
      // Ignored (401 handled globally by api-client authFailureHandler)
    }
  }, [user, activeProject]);

  const refreshProjects = useCallback(async () => {
    if (!getAccessToken() && !hasRefreshToken()) {
      return;
    }
    try {
      const list = await api.listProjects();
      setProjects(list);
      setActiveProject((prev) => {
        if (list.length === 0) return null;
        if (prev && list.some((p) => p.id === prev.id)) return prev;
        return list[0];
      });
    } catch {
      // Handled via global 401/error handling
    }
  }, []);

  useEffect(() => {
    setAuthFailureHandler(() => {
      clearAuthState();
      showToast("Session expired. Please sign in again.", "warning");
    });
    return () => setAuthFailureHandler(null);
  }, [clearAuthState, showToast]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrapSession() {
      // Unauthenticated visitors must not trigger protected API requests
      if (!getAccessToken() && !hasRefreshToken()) {
        clearSessionTokens();
        if (!cancelled) setAuthLoading(false);
        return;
      }

      try {
        if (!getAccessToken() && hasRefreshToken()) {
          const refreshed = await api.refresh();
          if (!refreshed) {
            if (!cancelled) {
              clearAuthState();
              setAuthLoading(false);
            }
            return;
          }
        }

        const me = await api.getMe();
        if (cancelled) return;
        setUser(me);
        await refreshProjects();
      } catch {
        if (!cancelled) {
          clearAuthState();
        }
      } finally {
        if (!cancelled) {
          setAuthLoading(false);
        }
      }
    }

    bootstrapSession();
    return () => {
      cancelled = true;
    };
  }, [clearAuthState, refreshProjects]);

  useEffect(() => {
    if (user && activeProject) {
      refreshPendingApprovals();
    } else {
      setPendingApprovalsCount(0);
    }
  }, [user, activeProject, refreshPendingApprovals]);

  const loginUser = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    setSessionTokens(res.access_token, res.refresh_token);
    const u = await api.getMe();
    setUser(u);
    await refreshProjects();
    showToast(`Signed in as ${u.username}`, "success");
  };

  const registerUser = async (email: string, username: string, password: string) => {
    await api.register({ email, username, password });
    await loginUser(email, password);
  };

  const logoutUser = async () => {
    const refresh = getRefreshToken();
    try {
      if (refresh) {
        await api.logout(refresh).catch(() => {});
      }
    } finally {
      clearAuthState();
      showToast("Signed out successfully", "info");
    }
  };

  return (
    <AppContext.Provider
      value={{
        user,
        authLoading,
        projects,
        activeProject,
        pendingApprovalsCount,
        activeView,
        setActiveView,
        setActiveProject,
        loginUser,
        registerUser,
        logoutUser,
        refreshProjects,
        refreshPendingApprovals,
        showToast,
      }}
    >
      {children}

      {/* Floating Toasts */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-3 rounded-lg border text-sm font-medium shadow-xl flex items-center justify-between transition-all ${
              t.type === "success"
                ? "bg-emerald-950/90 border-emerald-800 text-emerald-200"
                : t.type === "error"
                ? "bg-rose-950/90 border-rose-800 text-rose-200"
                : t.type === "warning"
                ? "bg-amber-950/90 border-amber-800 text-amber-200"
                : "bg-zinc-900/90 border-zinc-700 text-zinc-200"
            }`}
          >
            <span>{t.message}</span>
            <button
              onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
              className="ml-3 text-zinc-400 hover:text-zinc-100"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be used within an AppProvider");
  return context;
}
