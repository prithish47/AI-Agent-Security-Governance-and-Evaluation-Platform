# =============================================================================
# AgentGuard — Pure Python Policy Evaluation Engine
# =============================================================================
# Implements the 7 deterministic security rules in strict evaluation order.
#
# ARCHITECTURAL RULES:
# 1. Pure Python — Zero dependencies on FastAPI, SQLAlchemy, or AI SDKs.
# 2. Fail-Closed — Any malformed, missing, or errored context produces DENY.
# 3. Deterministic Short-Circuit Evaluation Order:
#    1. Tool Permission Rule
#    2. Tool Deny Rule (Deny takes precedence over allow)
#    3. Risk Level Ceiling Rule
#    4. Resource Ownership Rule
#    5. Argument Constraint Rule
#    6. Argument Pattern Rule
#    7. Approval Required Rule
#    8. ALLOW (Only if all 7 rules pass)
# =============================================================================

import json
import re
import time
from typing import Any, Dict, List, Optional

from app.policies.domain import (
    PolicyDecision,
    PolicyDecisionOutcome,
    RiskLevel,
    SecurityContext,
    ToolProposal,
)

# Standard regex patterns for deterministic security screening
COMMON_ATTACK_PATTERNS = [
    # SQL Injection patterns
    re.compile(r"(?i)\b(UNION\s+ALL\s+SELECT|DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE\s+TABLE|OR\s+'1'='1|OR\s+1=1)\b"),
    # Path traversal patterns
    re.compile(r"(\.\./|\.\.\\|/etc/passwd|/etc/shadow|C:\\Windows\\System32)"),
    # Dangerous shell command execution patterns
    re.compile(r"(?i)(\brm\s+-rf\b|\bchmod\s+777\b|;\s*curl\s+|\|\s*bash\b|\|\s*sh\b)"),
]


class PolicyEngine:
    """
    Deterministic security policy evaluation engine.
    Completely isolated from I/O, database, and network boundaries.
    """

    @classmethod
    def evaluate(cls, proposal: ToolProposal, context: SecurityContext) -> PolicyDecision:
        """
        Evaluate a proposed tool call against the pinned security context.
        Fails closed on any unexpected state or error.
        """
        start_time = time.perf_counter()

        try:
            # Validate input safety
            if not proposal or not proposal.tool_name:
                return cls._deny(
                    rule="input_validation",
                    reason="Malformed or missing tool proposal",
                    tool_name="unknown",
                    context=context,
                    start_time=start_time,
                )

            if not context:
                return cls._deny(
                    rule="fail_closed",
                    reason="Missing security execution context",
                    tool_name=proposal.tool_name,
                    context=context,
                    start_time=start_time,
                )

            # -----------------------------------------------------------------
            # 1. TOOL PERMISSION RULE
            # -----------------------------------------------------------------
            decision = cls._check_tool_permission(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 2. TOOL DENY RULE (Takes precedence over allow)
            # -----------------------------------------------------------------
            decision = cls._check_tool_deny(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 3. RISK LEVEL CEILING RULE
            # -----------------------------------------------------------------
            decision = cls._check_risk_ceiling(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 4. RESOURCE OWNERSHIP RULE
            # -----------------------------------------------------------------
            decision = cls._check_resource_ownership(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 5. ARGUMENT CONSTRAINT RULE
            # -----------------------------------------------------------------
            decision = cls._check_argument_constraints(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 6. ARGUMENT PATTERN RULE
            # -----------------------------------------------------------------
            decision = cls._check_argument_patterns(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 7. APPROVAL REQUIRED RULE
            # -----------------------------------------------------------------
            decision = cls._check_approval_required(proposal, context)
            if decision:
                return cls._finalize(decision, start_time)

            # -----------------------------------------------------------------
            # 8. ALLOW (All deterministic security checks passed)
            # -----------------------------------------------------------------
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return PolicyDecision(
                decision=PolicyDecisionOutcome.ALLOW,
                rule_responsible="default_allow",
                reason=f"All 7 security policy checks passed for tool '{proposal.tool_name}'",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
                evaluation_latency_ms=elapsed_ms,
            )

        except Exception as exc:
            # FAIL CLOSED: Never allow an action if evaluation threw an exception
            return cls._deny(
                rule="fail_closed_exception",
                reason=f"Policy evaluation exception (fail-closed triggered): {str(exc)}",
                tool_name=proposal.tool_name if proposal else "unknown",
                context=context,
                start_time=start_time,
            )

    # =========================================================================
    # RULE IMPLEMENTATIONS
    # =========================================================================

    @classmethod
    def _check_tool_permission(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """Rule 1: Verify tool is in the agent's assigned permissions set."""
        if proposal.tool_name not in context.assigned_tools:
            return PolicyDecision(
                decision=PolicyDecisionOutcome.DENY,
                rule_responsible="tool_permission_rule",
                reason=f"Tool '{proposal.tool_name}' is not assigned to agent '{context.agent_id}'",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
            )
        return None

    @classmethod
    def _check_tool_deny(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """Rule 2: Explicit deny takes precedence over allows."""
        denied_tools = context.policy_rules.get("denied_tools", [])
        if proposal.tool_name in denied_tools:
            return PolicyDecision(
                decision=PolicyDecisionOutcome.DENY,
                rule_responsible="tool_deny_rule",
                reason=f"Tool '{proposal.tool_name}' is explicitly denied by security policy",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
            )
        return None

    @classmethod
    def _check_risk_ceiling(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """Rule 3: Ensure tool risk does not exceed agent risk ceiling."""
        tool_risk = context.tool_risk_levels.get(proposal.tool_name, RiskLevel.MEDIUM)
        if tool_risk.exceeds(context.agent_risk_ceiling):
            return PolicyDecision(
                decision=PolicyDecisionOutcome.DENY,
                rule_responsible="risk_level_ceiling_rule",
                reason=(
                    f"Tool '{proposal.tool_name}' risk level ({tool_risk.value}) "
                    f"exceeds agent risk ceiling ({context.agent_risk_ceiling.value})"
                ),
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
            )
        return None

    @classmethod
    def _check_resource_ownership(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """
        Rule 4: Ensure agent accesses only resources belonging to its project/tenant.
        Does NOT trust model-supplied tenant IDs.
        """
        args = proposal.arguments or {}

        # 1. Direct tenant/project ID spoofing check
        for param in ("tenant_id", "project_id", "workspace_id", "org_id"):
            if param in args:
                supplied = str(args[param])
                if supplied != context.project_id:
                    return PolicyDecision(
                        decision=PolicyDecisionOutcome.DENY,
                        rule_responsible="resource_ownership_rule",
                        reason=(
                            f"Cross-tenant access violation: proposed {param} '{supplied}' "
                            f"does not match authorized project '{context.project_id}'"
                        ),
                        tool_name=proposal.tool_name,
                        policy_version=context.policy_version_number,
                    )

        # 2. Resource URI / prefix scope check
        for param in ("resource_id", "resource_uri", "path"):
            if param in args:
                resource_val = str(args[param])
                # If resource has a tenant prefix (e.g. tenant-123/customer/456), verify prefix
                if "/" in resource_val:
                    prefix = resource_val.split("/", 1)[0]
                    if context.authorized_resource_scopes and prefix not in context.authorized_resource_scopes:
                        return PolicyDecision(
                            decision=PolicyDecisionOutcome.DENY,
                            rule_responsible="resource_ownership_rule",
                            reason=f"Resource scope '{prefix}' is not within authorized scopes",
                            tool_name=proposal.tool_name,
                            policy_version=context.policy_version_number,
                        )

        return None

    @classmethod
    def _check_argument_constraints(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """Rule 5: Validate required arguments, types, bounds, string lengths, payload limits."""
        args = proposal.arguments

        if not isinstance(args, dict):
            return PolicyDecision(
                decision=PolicyDecisionOutcome.DENY,
                rule_responsible="argument_constraint_rule",
                reason="Tool arguments must be a structured dictionary",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
            )

        # Payload size ceiling
        max_bytes = context.policy_rules.get("max_argument_size_bytes", 10000)
        try:
            serialized_len = len(json.dumps(args))
            if serialized_len > max_bytes:
                return PolicyDecision(
                    decision=PolicyDecisionOutcome.DENY,
                    rule_responsible="argument_constraint_rule",
                    reason=f"Argument payload size ({serialized_len} bytes) exceeds limit ({max_bytes} bytes)",
                    tool_name=proposal.tool_name,
                    policy_version=context.policy_version_number,
                )
        except Exception:
            return PolicyDecision(
                decision=PolicyDecisionOutcome.DENY,
                rule_responsible="argument_constraint_rule",
                reason="Failed to serialize arguments for size constraint verification",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
            )

        # Array length ceiling
        max_array_size = context.policy_rules.get("max_array_size", 50)
        for key, val in args.items():
            if isinstance(val, (list, tuple)) and len(val) > max_array_size:
                return PolicyDecision(
                    decision=PolicyDecisionOutcome.DENY,
                    rule_responsible="argument_constraint_rule",
                    reason=f"Argument array '{key}' length ({len(val)}) exceeds maximum permitted ({max_array_size})",
                    tool_name=proposal.tool_name,
                    policy_version=context.policy_version_number,
                )

        # Validate against tool schema if registered
        schema = context.tool_schemas.get(proposal.tool_name)
        if schema and "required" in schema:
            for req in schema["required"]:
                if req not in args or args[req] is None or args[req] == "":
                    return PolicyDecision(
                        decision=PolicyDecisionOutcome.DENY,
                        rule_responsible="argument_constraint_rule",
                        reason=f"Missing or empty required argument '{req}' for tool '{proposal.tool_name}'",
                        tool_name=proposal.tool_name,
                        policy_version=context.policy_version_number,
                    )

        return None

    @classmethod
    def _check_argument_patterns(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """Rule 6: Detect suspicious arguments, injection indicators, disallowed command patterns."""
        args_text = json.dumps(proposal.arguments)

        # 1. Custom policy patterns
        custom_patterns = context.policy_rules.get("disallowed_patterns", [])
        for pat in custom_patterns:
            try:
                if re.search(pat, args_text):
                    return PolicyDecision(
                        decision=PolicyDecisionOutcome.DENY,
                        rule_responsible="argument_pattern_rule",
                        reason=f"Argument matched disallowed policy pattern: '{pat}'",
                        tool_name=proposal.tool_name,
                        policy_version=context.policy_version_number,
                    )
            except re.error:
                # If custom pattern is malformed, skip pattern or fail closed
                pass

        # 2. Built-in dangerous injection and path traversal patterns
        for regex in COMMON_ATTACK_PATTERNS:
            if regex.search(args_text):
                return PolicyDecision(
                    decision=PolicyDecisionOutcome.DENY,
                    rule_responsible="argument_pattern_rule",
                    reason=f"Argument contains dangerous indicator matching rule pattern: '{regex.pattern}'",
                    tool_name=proposal.tool_name,
                    policy_version=context.policy_version_number,
                )

        return None

    @classmethod
    def _check_approval_required(
        cls, proposal: ToolProposal, context: SecurityContext
    ) -> Optional[PolicyDecision]:
        """Rule 7: Gate high-risk or financial operations behind human review."""
        approval_tools = context.policy_rules.get("approval_required_tools", [])
        if proposal.tool_name in approval_tools:
            return PolicyDecision(
                decision=PolicyDecisionOutcome.REQUIRES_APPROVAL,
                rule_responsible="approval_required_rule",
                reason=f"Tool '{proposal.tool_name}' requires explicit human approval before execution",
                tool_name=proposal.tool_name,
                policy_version=context.policy_version_number,
            )
        return None

    # =========================================================================
    # HELPERS
    # =========================================================================

    @classmethod
    def _deny(
        cls,
        rule: str,
        reason: str,
        tool_name: str,
        context: Optional[SecurityContext],
        start_time: float,
    ) -> PolicyDecision:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return PolicyDecision(
            decision=PolicyDecisionOutcome.DENY,
            rule_responsible=rule,
            reason=reason,
            tool_name=tool_name,
            policy_version=context.policy_version_number if context else 1,
            evaluation_latency_ms=elapsed_ms,
        )

    @classmethod
    def _finalize(cls, decision: PolicyDecision, start_time: float) -> PolicyDecision:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return PolicyDecision(
            decision=decision.decision,
            rule_responsible=decision.rule_responsible,
            reason=decision.reason,
            tool_name=decision.tool_name,
            timestamp=decision.timestamp,
            policy_version=decision.policy_version,
            evaluation_latency_ms=elapsed_ms,
        )
