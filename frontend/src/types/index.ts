// =============================================================================
// AgentGuard — Frontend TypeScript Types
// =============================================================================

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ProjectRole = "OWNER" | "ADMIN" | "DEVELOPER" | "APPROVER" | "VIEWER";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED" | "CONSUMED";
export type AuditSeverity = "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type ExecutionStatus =
  | "RUNNING"
  | "COMPLETED"
  | "DENIED"
  | "REQUIRES_APPROVAL"
  | "MAX_ITERATIONS_REACHED"
  | "MODEL_ERROR"
  | "TOOL_ERROR"
  | "SECURITY_ERROR";

export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: ProjectRole;
  created_at: string;
}

export interface Agent {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  system_prompt: string;
  model_provider: string;
  model_name: string;
  max_iterations: number;
  max_risk_level: RiskLevel;
  policy_id?: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolDefinition {
  id: string;
  project_id: string;
  name: string;
  description: string;
  input_schema: Record<string, any>;
  risk_level: RiskLevel;
  is_enabled: boolean;
  is_executable: boolean;
  created_at: string;
  updated_at: string;
}

export interface SecurityPolicy {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  active_version_id?: string;
  created_at: string;
  updated_at: string;
}

export interface PolicyVersion {
  id: string;
  policy_id: string;
  version_number: number;
  rules: Record<string, any>;
  is_active: boolean;
  created_by?: string;
  created_at: string;
}

export interface ExecutionStep {
  id: string;
  step_number: number;
  step_type: string;
  tool_name?: string;
  tool_arguments?: Record<string, any>;
  policy_decision?: string;
  policy_rule?: string;
  policy_reason?: string;
  tool_result?: Record<string, any>;
  model_response?: string;
  policy_eval_ms?: number;
  created_at: string;
}

export interface Execution {
  id: string;
  project_id: string;
  agent_id: string;
  task_prompt: string;
  status: ExecutionStatus;
  termination_reason?: string;
  final_response?: string;
  iteration_count: number;
  started_at: string;
  completed_at?: string;
}

export interface ExecutionTrace {
  execution: Execution;
  steps: ExecutionStep[];
}

export interface ApprovalRequest {
  id: string;
  project_id: string;
  execution_id: string;
  agent_id: string;
  tool_name: string;
  tool_arguments: Record<string, any>;
  action_hash: string;
  status: ApprovalStatus;
  reviewed_by?: string;
  review_note?: string;
  created_at: string;
  reviewed_at?: string;
  expires_at?: string;
}

export interface AuditEvent {
  id: string;
  project_id: string;
  actor_id?: string;
  execution_id?: string;
  event_type: string;
  severity: AuditSeverity;
  event_metadata: Record<string, any>;
  created_at: string;
}

export interface BenchmarkMetrics {
  asr: number | null;
  uter: number | null;
  ltsr: number | null;
  fbr: number | null;
  policy_latency_p50_ms: number | null;
  policy_latency_p95_ms: number | null;
  policy_latency_max_ms: number | null;
}

export interface EvaluationRun {
  id: string;
  suite_id: string;
  project_id: string;
  agent_id: string;
  mode: "baseline" | "protected" | "both";
  status: string;
  metrics: {
    baseline?: BenchmarkMetrics;
    protected?: BenchmarkMetrics;
  };
  started_at: string;
  completed_at?: string;
}

export interface EvaluationResult {
  id: string;
  run_id: string;
  case_id: string;
  actual_result: string;
  attack_succeeded: boolean;
  tool_executed: boolean;
  legitimate_succeeded: boolean;
  false_blocked: boolean;
  execution_latency_ms: number;
  policy_eval_latency_ms?: number;
  failure_reason?: string;
  created_at: string;
}
