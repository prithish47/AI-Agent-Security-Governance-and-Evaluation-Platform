# =============================================================================
# AgentGuard — Persistence Layer (SQLAlchemy 2.0 Models)
# =============================================================================
# This module defines the complete relational schema for AgentGuard.
#
# DESIGN HIGHLIGHTS:
# 1. UUID primary keys across all tables for strong security and uniqueness.
# 2. Strict foreign keys with cascade rules ensuring relational integrity.
# 3. Explicit composite unique constraints for tenant and assignment isolation:
#    - UNIQUE(project_id, user_id) on project_members
#    - UNIQUE(project_id, name) on tool_definitions
#    - UNIQUE(project_id, name) on agents
#    - UNIQUE(agent_id, tool_id) on agent_tool_assignments
# 4. JSONB for flexible policy snapshots, tool argument records, and schemas,
#    with SQLite JSON fallback for in-memory unit tests.
# 5. Immutable policy versions and append-only audit trail records.
# =============================================================================

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Cross-dialect JSON type: JSONB on PostgreSQL, JSON on SQLite/others
JSON_TYPE = JSONB().with_variant(sa.JSON(), "sqlite")


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


# =============================================================================
# ENUMS
# =============================================================================

class ProjectRole(str, enum.Enum):
    """5-tier RBAC Project Roles."""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    APPROVER = "APPROVER"
    VIEWER = "VIEWER"


class RiskLevel(str, enum.Enum):
    """Tool and agent risk classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, enum.Enum):
    """Lifecycle states for human approval requests."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class AuditSeverity(str, enum.Enum):
    """Severity classification for security audit events."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExecutionStatus(str, enum.Enum):
    """Execution state / termination reason."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    MAX_ITERATIONS_REACHED = "MAX_ITERATIONS_REACHED"
    MODEL_ERROR = "MODEL_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    SECURITY_ERROR = "SECURITY_ERROR"


class EvaluationMode(str, enum.Enum):
    """Evaluation benchmark run mode."""
    BASELINE = "baseline"
    PROTECTED = "protected"
    BOTH = "both"


# =============================================================================
# 1. USER & AUTHENTICATION
# =============================================================================

class User(Base):
    """User account model for authentication and identity."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    memberships: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """Hashed refresh tokens for secure JWT refresh with revocation capability."""
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


# =============================================================================
# 2. PROJECTS & MEMBERSHIPS (Multi-Tenancy)
# =============================================================================

class Project(Base):
    """Tenant/workspace workspace container."""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    members: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    agents: Mapped[List["Agent"]] = relationship("Agent", back_populates="project", cascade="all, delete-orphan")
    tools: Mapped[List["ToolDefinition"]] = relationship("ToolDefinition", back_populates="project", cascade="all, delete-orphan")
    policies: Mapped[List["SecurityPolicy"]] = relationship("SecurityPolicy", back_populates="project", cascade="all, delete-orphan")
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="project", cascade="all, delete-orphan")
    approval_requests: Mapped[List["ApprovalRequest"]] = relationship("ApprovalRequest", back_populates="project", cascade="all, delete-orphan")
    audit_events: Mapped[List["AuditEvent"]] = relationship("AuditEvent", back_populates="project", cascade="all, delete-orphan")
    evaluation_suites: Mapped[List["EvaluationSuite"]] = relationship("EvaluationSuite", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    """User membership in a project with a specific RBAC role."""
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole, name="project_role_enum", native_enum=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


# =============================================================================
# 3. TOOLS & CATALOG
# =============================================================================

class ToolDefinition(Base):
    """
    Metadata representation of an executable tool within a project.
    
    CRITICAL SECURITY RULE:
    Database tool definitions never contain arbitrary Python code or scripts.
    Actual execution logic exists in a precompiled registered Python catalog.
    """
    __tablename__ = "tool_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_tool_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level_enum", native_enum=False), default=RiskLevel.LOW, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="tools")
    agent_assignments: Mapped[List["AgentToolAssignment"]] = relationship("AgentToolAssignment", back_populates="tool", cascade="all, delete-orphan")


# =============================================================================
# 4. POLICIES & POLICY VERSIONS (Immutable Snapshots)
# =============================================================================

class SecurityPolicy(Base):
    """Container for security policy configurations within a project."""
    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="policies")
    versions: Mapped[List["PolicyVersion"]] = relationship("PolicyVersion", back_populates="policy", cascade="all, delete-orphan")
    agents: Mapped[List["Agent"]] = relationship("Agent", back_populates="policy")


class PolicyVersion(Base):
    """
    Immutable versioned snapshot of deterministic security rules.
    
    Once written, rules in a policy version are NEVER updated in place.
    Any policy changes create a new PolicyVersion with an incremented version_number.
    """
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version_number", name="uq_policy_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("security_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rules: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    policy: Mapped["SecurityPolicy"] = relationship("SecurityPolicy", back_populates="versions")


# =============================================================================
# 5. AGENTS & AGENT-TOOL ASSIGNMENTS
# =============================================================================

class Agent(Base):
    """AI agent configuration with security boundary parameters."""
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_agent_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="You are a secure, helpful AI assistant.")
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="mock-model")
    max_iterations: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="agent_max_risk_enum", native_enum=False), default=RiskLevel.MEDIUM, nullable=False)
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("security_policies.id", ondelete="SET NULL"), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="agents")
    policy: Mapped[Optional["SecurityPolicy"]] = relationship("SecurityPolicy", back_populates="agents")
    tool_assignments: Mapped[List["AgentToolAssignment"]] = relationship("AgentToolAssignment", back_populates="agent", cascade="all, delete-orphan")
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="agent", cascade="all, delete-orphan")


class AgentToolAssignment(Base):
    """Explicit permission binding between an agent and an authorized tool."""
    __tablename__ = "agent_tool_assignments"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool_assignment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tool_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="tool_assignments")
    tool: Mapped["ToolDefinition"] = relationship("ToolDefinition", back_populates="agent_assignments")


# =============================================================================
# 6. EXECUTIONS & AUDIT TRACES
# =============================================================================

class Execution(Base):
    """Record of an orchestrated agent execution session."""
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    task_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus, name="execution_status_enum", native_enum=False), default=ExecutionStatus.RUNNING, nullable=False, index=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    context_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    final_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="executions")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="executions")
    steps: Mapped[List["ExecutionStep"]] = relationship("ExecutionStep", back_populates="execution", cascade="all, delete-orphan", order_by="ExecutionStep.step_number")
    approval_requests: Mapped[List["ApprovalRequest"]] = relationship("ApprovalRequest", back_populates="execution", cascade="all, delete-orphan")


class ExecutionStep(Base):
    """Detailed trace step within an execution."""
    __tablename__ = "execution_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)  # TOOL_CALL, FINAL_ANSWER, ERROR
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_arguments: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    policy_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # ALLOW, DENY, REQUIRES_APPROVAL
    policy_rule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    model_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_eval_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    execution: Mapped["Execution"] = relationship("Execution", back_populates="steps")


# =============================================================================
# 7. HUMAN APPROVAL REQUESTS (Cryptographic Binding)
# =============================================================================

class ApprovalRequest(Base):
    """
    Suspended high-risk operation awaiting human review.
    
    Integrity is protected by RFC 8785 Canonical JSON hashing (action_hash).
    Resumption verifies action_hash before atomic single-use consumption.
    """
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_arguments: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False)
    action_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256 of canonical RFC 8785 JSON
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus, name="approval_status_enum", native_enum=False), default=ApprovalStatus.PENDING, nullable=False, index=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="approval_requests")
    execution: Mapped["Execution"] = relationship("Execution", back_populates="approval_requests")


# =============================================================================
# 8. AUDIT EVENTS (Append-Only Log)
# =============================================================================

class AuditEvent(Base):
    """Append-only security event audit log record."""
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("executions.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[AuditSeverity] = mapped_column(Enum(AuditSeverity, name="audit_severity_enum", native_enum=False), default=AuditSeverity.INFO, nullable=False, index=True)
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    project: Mapped["Project"] = relationship("Project", back_populates="audit_events")


# =============================================================================
# 9. EVALUATIONS & BENCHMARK SUITES
# =============================================================================

class EvaluationSuite(Base):
    """Container for benchmark test suites (e.g. 21-case adversarial suite)."""
    __tablename__ = "evaluation_suites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="evaluation_suites")
    cases: Mapped[List["EvaluationCase"]] = relationship("EvaluationCase", back_populates="suite", cascade="all, delete-orphan")
    runs: Mapped[List["EvaluationRun"]] = relationship("EvaluationRun", back_populates="suite", cascade="all, delete-orphan")


class EvaluationCase(Base):
    """Individual benchmark scenario (adversarial or legitimate)."""
    __tablename__ = "evaluation_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evaluation_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # ADVERSARIAL or LEGITIMATE
    attack_type: Mapped[str] = mapped_column(String(100), nullable=False)  # DIRECT_PROMPT_INJECTION, etc.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    test_config: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    expected_result: Mapped[str] = mapped_column(String(50), nullable=False)  # DENY, ALLOW, REQUIRES_APPROVAL
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    suite: Mapped["EvaluationSuite"] = relationship("EvaluationSuite", back_populates="cases")
    results: Mapped[List["EvaluationResult"]] = relationship("EvaluationResult", back_populates="case", cascade="all, delete-orphan")


class EvaluationRun(Base):
    """Execution run of an evaluation suite comparing baseline and protected agent behaviors."""
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evaluation_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[EvaluationMode] = mapped_column(Enum(EvaluationMode, name="evaluation_mode_enum", native_enum=False), default=EvaluationMode.BOTH, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="RUNNING", nullable=False)  # RUNNING, COMPLETED, FAILED
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON_TYPE, nullable=False, default=dict)  # ASR, UTER, LTSR, FBR, latency percentiles
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    suite: Mapped["EvaluationSuite"] = relationship("EvaluationSuite", back_populates="runs")
    results: Mapped[List["EvaluationResult"]] = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")


class EvaluationResult(Base):
    """Detailed outcome of a single benchmark test case execution."""
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    actual_result: Mapped[str] = mapped_column(String(50), nullable=False)
    attack_succeeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tool_executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legitimate_succeeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    false_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    policy_eval_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="results")
    case: Mapped["EvaluationCase"] = relationship("EvaluationCase", back_populates="results")
