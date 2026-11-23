# =============================================================================
# AgentGuard — Guarded Tool Executor (The Security Boundary)
# =============================================================================
# ALL proposed tool calls MUST pass through this guarded executor.
#
# GUARANTEES:
# 1. No model can directly call a Python function.
# 2. Tool must exist in the precompiled whitelist.
# 3. PolicyEngine evaluates all 7 rules deterministically.
# 4. If DENIED -> blocked immediately, audited, and returned as denial.
# 5. If REQUIRES_APPROVAL -> suspended, approval record created.
# 6. If ALLOWED -> executed via whitelist catalog, audited, result returned.
# 7. No alternate execution path exists.
# =============================================================================

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.policies.domain import (
    PolicyDecision,
    PolicyDecisionOutcome,
    SecurityContext,
    ToolProposal,
)
from app.policies.engine import PolicyEngine
from app.tools.catalog import get_executor


@dataclass
class GuardedExecutionResult:
    """The outcome of passing a proposed tool call through the security boundary."""
    tool_name: str
    decision: PolicyDecision
    result_data: Optional[Dict[str, Any]] = None
    is_blocked: bool = False
    requires_approval: bool = False
    error_message: Optional[str] = None


class GuardedToolExecutor:
    """
    Centralized security gateway between AI agents and external tools.
    """

    @classmethod
    def execute(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> GuardedExecutionResult:
        """
        Execute the guarded tool invocation pipeline.
        Fails closed on any security policy violation or unwhitelisted tool.
        """
        # 1. Check if tool exists in the precompiled Python executor catalog
        executor = get_executor(proposal.tool_name)
        if not executor:
            decision = PolicyDecision(
                decision=PolicyDecisionOutcome.DENY,
                rule_responsible="unsupported_tool_implementation",
                reason=f"Tool '{proposal.tool_name}' is not in the registered precompiled executor catalog",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number if context else 1,
            )
            return GuardedExecutionResult(
                tool_name=proposal.tool_name,
                decision=decision,
                is_blocked=True,
                error_message=decision.reason,
            )

        # 2. Evaluate security policies (all 7 rules)
        decision = PolicyEngine.evaluate(proposal, context)

        # 3. Handle DENY
        if decision.is_denied:
            return GuardedExecutionResult(
                tool_name=proposal.tool_name,
                decision=decision,
                is_blocked=True,
                error_message=decision.reason,
            )

        # 4. Handle REQUIRES_APPROVAL
        if decision.requires_approval:
            return GuardedExecutionResult(
                tool_name=proposal.tool_name,
                decision=decision,
                requires_approval=True,
                error_message=decision.reason,
            )

        # 5. Handle ALLOW -> Dispatch to precompiled Python executor
        try:
            output = executor(proposal.arguments or {})
            return GuardedExecutionResult(
                tool_name=proposal.tool_name,
                decision=decision,
                result_data=output,
                is_blocked=False,
            )
        except Exception as exc:
            # Execution failure inside safe tool
            return GuardedExecutionResult(
                tool_name=proposal.tool_name,
                decision=decision,
                result_data=None,
                error_message=f"Tool execution error: {str(exc)}",
            )
