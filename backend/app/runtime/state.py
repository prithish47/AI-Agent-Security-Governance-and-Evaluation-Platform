# =============================================================================
# AgentGuard — Execution State Machine Transitions
# =============================================================================
# Enforces valid lifecycle transitions between Execution states:
# RUNNING -> REQUIRES_APPROVAL -> RUNNING -> COMPLETED / FAILED / CANCELLED / etc.
# Terminal states (COMPLETED, DENIED, MAX_ITERATIONS_REACHED, MODEL_ERROR, TOOL_ERROR,
# FAILED, CANCELLED) cannot transition to any other state.
# =============================================================================

from typing import Dict, Set

from app.core.exceptions import ConflictError
from app.persistence.models import ExecutionStatus

VALID_EXECUTION_TRANSITIONS: Dict[ExecutionStatus, Set[ExecutionStatus]] = {
    ExecutionStatus.RUNNING: {
        ExecutionStatus.REQUIRES_APPROVAL,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.DENIED,
        ExecutionStatus.MAX_ITERATIONS_REACHED,
        ExecutionStatus.MODEL_ERROR,
        ExecutionStatus.TOOL_ERROR,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.REQUIRES_APPROVAL: {
        ExecutionStatus.RUNNING,      # Valid resumption after approval
        ExecutionStatus.DENIED,       # Reviewer rejected action
        ExecutionStatus.CANCELLED,    # Cancelled or expired
        ExecutionStatus.FAILED,       # Security violation or failure
        ExecutionStatus.TOOL_ERROR,   # Tool error during immediate post-approval execution
    },
    # Terminal states:
    ExecutionStatus.COMPLETED: set(),
    ExecutionStatus.DENIED: set(),
    ExecutionStatus.MAX_ITERATIONS_REACHED: set(),
    ExecutionStatus.MODEL_ERROR: set(),
    ExecutionStatus.TOOL_ERROR: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
    ExecutionStatus.SECURITY_ERROR: set(),
}


def validate_execution_transition(current: ExecutionStatus, target: ExecutionStatus) -> None:
    """
    Validate that transitioning an Execution from `current` to `target` status is permitted.
    Raises ConflictError if the transition is prohibited.
    """
    if current == target:
        return

    allowed = VALID_EXECUTION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ConflictError(
            f"Invalid execution state transition from '{current.value}' to '{target.value}'"
        )
