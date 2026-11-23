// =============================================================================
// AgentGuard — Human Approvals View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { ApprovalRequest } from "@/types";
import {
  ClockAlert,
  CheckCircle2,
  XCircle,
  Hash,
  ArrowRight,
  Loader2,
  ShieldAlert,
  Play,
  RotateCw,
} from "lucide-react";

export default function ApprovalsView() {
  const { activeProject, refreshPendingApprovals, showToast } = useApp();
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [filterStatus, setFilterStatus] = useState<string>("PENDING");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState<Record<string, string>>({});

  const loadApprovals = async () => {
    if (!activeProject) return;
    setLoading(true);
    try {
      const data = await api.listApprovals(activeProject.id, filterStatus || undefined);
      setApprovals(data);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, [activeProject, filterStatus]);

  const handleApprove = async (approvalId: string) => {
    setActionLoading(approvalId);
    try {
      const note = reviewNote[approvalId] || "Approved via AgentGuard Governance Console";
      await api.approveAction(approvalId, note);
      showToast("High-risk action approved", "success");
      await refreshPendingApprovals();
      await loadApprovals();
    } catch (err: any) {
      showToast(err.message || "Failed to approve action", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (approvalId: string) => {
    setActionLoading(approvalId);
    try {
      const note = reviewNote[approvalId] || "Rejected by Security Operator";
      await api.rejectAction(approvalId, note);
      showToast("Action rejected", "info");
      await refreshPendingApprovals();
      await loadApprovals();
    } catch (err: any) {
      showToast(err.message || "Failed to reject action", "error");
    } finally {
      setActionLoading(null);
    }
  };

  const handleResume = async (approvalId: string) => {
    setActionLoading(approvalId);
    try {
      await api.resumeApprovedAction(approvalId);
      showToast("Agent execution resumed and completed", "success");
      await refreshPendingApprovals();
      await loadApprovals();
    } catch (err: any) {
      showToast(err.message || "Failed to resume execution", "error");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <ClockAlert className="w-5 h-5 text-amber-500" />
            Human-in-the-Loop Approval Queue
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            RFC 8785 canonical hash binding ensures proposals cannot be tampered with prior to authorized execution.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-lg p-1 text-xs">
          <button
            onClick={() => setFilterStatus("PENDING")}
            className={`px-3 py-1 rounded-md font-medium transition-colors ${
              filterStatus === "PENDING"
                ? "bg-amber-500/20 text-amber-300 font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Pending
          </button>
          <button
            onClick={() => setFilterStatus("APPROVED")}
            className={`px-3 py-1 rounded-md font-medium transition-colors ${
              filterStatus === "APPROVED"
                ? "bg-emerald-500/20 text-emerald-300 font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Approved
          </button>
          <button
            onClick={() => setFilterStatus("REJECTED")}
            className={`px-3 py-1 rounded-md font-medium transition-colors ${
              filterStatus === "REJECTED"
                ? "bg-rose-500/20 text-rose-300 font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Rejected
          </button>
        </div>
      </div>

      {/* Approvals List */}
      {loading ? (
        <div className="py-12 flex justify-center text-zinc-500 text-xs">Loading approval requests...</div>
      ) : approvals.length === 0 ? (
        <div className="p-12 text-center bg-zinc-900 border border-dashed border-zinc-800 rounded-xl text-zinc-500 text-xs">
          No {filterStatus.toLowerCase()} approvals found for this workspace.
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map((req) => (
            <div
              key={req.id}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-sm text-zinc-200">{req.tool_name}</span>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      req.status === "PENDING"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : req.status === "APPROVED"
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                    }`}
                  >
                    {req.status}
                  </span>
                </div>
                <span className="text-[11px] font-mono text-zinc-500">
                  {new Date(req.created_at).toLocaleString()}
                </span>
              </div>

              {/* Canonical Hash Display */}
              <div className="p-2.5 rounded-lg bg-zinc-950 border border-zinc-800/80 font-mono text-[11px] flex items-center justify-between text-zinc-400">
                <div className="flex items-center gap-2 truncate">
                  <Hash className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                  <span className="text-zinc-500">RFC 8785 SHA-256:</span>
                  <span className="text-blue-400 truncate">{req.action_hash}</span>
                </div>
                <span className="text-zinc-500 text-[10px] shrink-0 ml-2">Tamper Proof</span>
              </div>

              {/* Arguments JSON */}
              <div>
                <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                  Proposed Arguments
                </div>
                <pre className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-300 overflow-x-auto">
                  {JSON.stringify(req.tool_arguments, null, 2)}
                </pre>
              </div>

              {/* Actions */}
              {req.status === "PENDING" && (
                <div className="pt-2 flex flex-col md:flex-row items-center gap-3">
                  <input
                    type="text"
                    placeholder="Optional review justification / note..."
                    value={reviewNote[req.id] || ""}
                    onChange={(e) => setReviewNote({ ...reviewNote, [req.id]: e.target.value })}
                    className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-hidden focus:border-blue-500"
                  />
                  <div className="flex gap-2 w-full md:w-auto">
                    <button
                      onClick={() => handleReject(req.id)}
                      disabled={actionLoading === req.id}
                      className="flex-1 md:flex-initial px-4 py-1.5 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 hover:bg-rose-900/50 text-xs font-medium transition-colors"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleApprove(req.id)}
                      disabled={actionLoading === req.id}
                      className="flex-1 md:flex-initial px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all flex items-center justify-center gap-1.5"
                    >
                      {actionLoading === req.id && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      Approve Action
                    </button>
                  </div>
                </div>
              )}

              {req.status === "APPROVED" && (
                <div className="pt-2 flex justify-end">
                  <button
                    onClick={() => handleResume(req.id)}
                    disabled={actionLoading === req.id}
                    className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 flex items-center gap-1.5 transition-all"
                  >
                    {actionLoading === req.id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5 fill-current" />
                    )}
                    Resume & Execute Proposal
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
