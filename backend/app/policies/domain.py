# =============================================================================
# AgentGuard — Pure Python Policy Domain Models
# =============================================================================
# CRITICAL ARCHITECTURAL REQUIREMENT:
# This module has ZERO dependencies on FastAPI, SQLAlchemy, or AI providers.
# It is pure, portable Python domain logic.
# =============================================================================

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class PolicyDecisionOutcome(str, Enum):
    """The 3 mutually exclusive policy decision outcomes."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


class RiskLevel(str, Enum):
    """Risk tiers for tools and agent ceilings."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        """Numeric rank for ceiling comparisons: LOW (1) < MEDIUM (2) < HIGH (3) < CRITICAL (4)."""
        ranks = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        return ranks[self]

    def exceeds(self, other: "RiskLevel") -> bool:
        """Return True if self has higher risk rank than other."""
        return self.rank > other.rank


@dataclass(frozen=True)
class ToolProposal:
    """An untrusted tool call proposal produced by an AI model."""
    tool_name: str
    arguments: Dict[str, Any]
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class SecurityContext:
    """
    Immutable pinned execution context snapshot for policy evaluation.
    Does NOT depend on database queries or external network requests.
    """
    agent_id: str
    project_id: str
    assigned_tools: Set[str]
    agent_risk_ceiling: RiskLevel
    tool_risk_levels: Dict[str, RiskLevel] = field(default_factory=dict)
    tool_schemas: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    policy_rules: Dict[str, Any] = field(default_factory=dict)
    policy_version_number: int = 1
    authorized_resource_scopes: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class PolicyDecision:
    """The deterministic outcome of evaluating a tool proposal against security policies."""
    decision: PolicyDecisionOutcome
    rule_responsible: str
    reason: str
    tool_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy_version: int = 1
    evaluation_latency_ms: float = 0.0

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecisionOutcome.ALLOW

    @property
    def is_denied(self) -> bool:
        return self.decision == PolicyDecisionOutcome.DENY

    @property
    def requires_approval(self) -> bool:
        return self.decision == PolicyDecisionOutcome.REQUIRES_APPROVAL
