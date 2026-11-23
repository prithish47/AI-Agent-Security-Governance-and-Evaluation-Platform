// =============================================================================
// AgentGuard — Audit Logs View
// =============================================================================

"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import api from "@/lib/api-client";
import { AuditEvent, AuditSeverity } from "@/types";
import { ScrollText, Filter, ChevronLeft, ChevronRight, AlertCircle, ShieldAlert, Check } from "lucide-react";

export default function AuditLogsView() {
  const { activeProject } = useApp();
  const [logs, setLogs] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<AuditEvent | null>(null);

  const loadAuditLogs = async () => {
    if (!activeProject) return;
    setLoading(true);
    try {
      const filters: Record<string, string> | undefined = severityFilter ? { severity: severityFilter } : undefined;
      const res = await api.listAuditLogs(activeProject.id, page, 25, filters);
      setLogs(res.items);
      setTotal(res.total);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, [activeProject, page, severityFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <ScrollText className="w-5 h-5 text-blue-500" />
            Security Audit Trail
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Immutable log of all policy evaluations, security denials, human approvals, and executions.
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300">
            <Filter className="w-3.5 h-3.5 text-zinc-500" />
            <select
              value={severityFilter}
              onChange={(e) => {
                setSeverityFilter(e.target.value);
                setPage(1);
              }}
              className="bg-transparent focus:outline-hidden text-xs"
            >
              <option value="" className="bg-zinc-900">All Severities</option>
              <option value="INFO" className="bg-zinc-900">INFO</option>
              <option value="WARNING" className="bg-zinc-900">WARNING</option>
              <option value="ERROR" className="bg-zinc-900">ERROR</option>
              <option value="CRITICAL" className="bg-zinc-900">CRITICAL</option>
            </select>
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-zinc-500 text-xs">Loading audit events...</div>
        ) : logs.length === 0 ? (
          <div className="py-12 text-center text-zinc-500 text-xs">No audit events found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-zinc-950 text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Execution Ref</th>
                  <th className="py-3 px-4">Metadata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelectedLog(log)}
                    className="hover:bg-zinc-950/60 cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 px-4 text-zinc-400">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-sm text-[10px] font-bold ${
                          log.severity === "CRITICAL"
                            ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            : log.severity === "ERROR"
                            ? "bg-red-500/20 text-red-300 border border-red-500/30"
                            : log.severity === "WARNING"
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                        }`}
                      >
                        {log.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-zinc-200 font-semibold">{log.event_type}</td>
                    <td className="py-2.5 px-4 text-zinc-500">
                      {log.actor_id ? `${log.actor_id.slice(0, 8)}...` : "SYSTEM"}
                    </td>
                    <td className="py-2.5 px-4 text-zinc-500">
                      {log.execution_id ? `${log.execution_id.slice(0, 8)}...` : "—"}
                    </td>
                    <td className="py-2.5 px-4 text-zinc-400 truncate max-w-xs">
                      {JSON.stringify(log.event_metadata)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="p-3 bg-zinc-950 border-t border-zinc-800 flex items-center justify-between text-xs text-zinc-500">
          <span>
            Total Events: <strong className="text-zinc-300">{total}</strong>
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded-md hover:bg-zinc-800 disabled:opacity-30 text-zinc-300"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-mono text-zinc-300">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 25 >= total}
              className="p-1 rounded-md hover:bg-zinc-800 disabled:opacity-30 text-zinc-300"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Selected Metadata Inspector Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <h2 className="text-base font-bold text-zinc-100 font-mono mb-1">
              Audit Event: {selectedLog.event_type}
            </h2>
            <div className="text-xs text-zinc-500 mb-4 font-mono">
              Timestamp: {new Date(selectedLog.created_at).toISOString()}
            </div>

            <pre className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 text-xs font-mono text-zinc-300 overflow-x-auto max-h-80">
              {JSON.stringify(selectedLog, null, 2)}
            </pre>

            <div className="mt-4 pt-3 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
