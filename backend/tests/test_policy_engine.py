# =============================================================================
# AgentGuard — Comprehensive Pure Python Policy Engine & Guarded Executor Tests
# =============================================================================
# Verifies all 7 policy rules, evaluation order, fail-closed behavior, and
# GuardedToolExecutor security boundary without requiring any database or network.
# =============================================================================

import pytest

from app.policies.domain import (
    PolicyDecisionOutcome,
    RiskLevel,
    SecurityContext,
    ToolProposal,
)
from app.policies.engine import PolicyEngine
from app.tools.guarded_executor import GuardedToolExecutor


@pytest.fixture
def base_context() -> SecurityContext:
    """Fixture providing a standard, authorized security context."""
    return SecurityContext(
        agent_id="agent-support-1",
        project_id="proj-tenant-100",
        assigned_tools={"search_customer", "get_support_ticket", "get_order_status", "calculate_refund", "issue_refund"},
        agent_risk_ceiling=RiskLevel.HIGH,
        tool_risk_levels={
            "search_customer": RiskLevel.LOW,
            "get_support_ticket": RiskLevel.LOW,
            "get_order_status": RiskLevel.LOW,
            "calculate_refund": RiskLevel.MEDIUM,
            "issue_refund": RiskLevel.HIGH,
            "delete_database": RiskLevel.CRITICAL,
        },
        tool_schemas={
            "search_customer": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "issue_refund": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}},
                "required": ["order_id", "amount"],
            },
        },
        policy_rules={
            "denied_tools": ["delete_database", "export_all_customers"],
            "approval_required_tools": ["issue_refund"],
            "max_argument_size_bytes": 1000,
            "max_array_size": 10,
            "disallowed_patterns": [r"(?i)admin_override=true"],
        },
        policy_version_number=1,
        authorized_resource_scopes={"proj-tenant-100", "corp-public"},
    )


# =============================================================================
# 1. TOOL PERMISSION RULE TESTS
# =============================================================================

def test_rule_1_assigned_tool_passes(base_context: SecurityContext):
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": "Alice"})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_allowed
    assert decision.decision == PolicyDecisionOutcome.ALLOW


def test_rule_1_unassigned_tool_denied(base_context: SecurityContext):
    proposal = ToolProposal(tool_name="unassigned_secret_tool", arguments={})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "tool_permission_rule"
    assert "not assigned" in decision.reason


# =============================================================================
# 2. TOOL DENY RULE TESTS (Explicit Deny Takes Precedence)
# =============================================================================

def test_rule_2_explicit_deny_blocks_tool(base_context: SecurityContext):
    # Even if delete_database were somehow in assigned_tools, explicit deny blocks it
    context = SecurityContext(
        agent_id=base_context.agent_id,
        project_id=base_context.project_id,
        assigned_tools={"delete_database"},
        agent_risk_ceiling=RiskLevel.CRITICAL,
        policy_rules={"denied_tools": ["delete_database"]},
    )
    proposal = ToolProposal(tool_name="delete_database", arguments={})
    decision = PolicyEngine.evaluate(proposal, context)
    assert decision.is_denied
    assert decision.rule_responsible == "tool_deny_rule"
    assert "explicitly denied" in decision.reason


def test_rule_2_deny_precedes_approval(base_context: SecurityContext):
    # Tool in both denied_tools and approval_required_tools -> MUST DENY
    context = SecurityContext(
        agent_id=base_context.agent_id,
        project_id=base_context.project_id,
        assigned_tools={"dangerous_tool"},
        agent_risk_ceiling=RiskLevel.CRITICAL,
        policy_rules={
            "denied_tools": ["dangerous_tool"],
            "approval_required_tools": ["dangerous_tool"],
        },
    )
    proposal = ToolProposal(tool_name="dangerous_tool", arguments={})
    decision = PolicyEngine.evaluate(proposal, context)
    assert decision.is_denied
    assert decision.rule_responsible == "tool_deny_rule"


# =============================================================================
# 3. RISK LEVEL CEILING RULE TESTS
# =============================================================================

def test_rule_3_risk_level_within_ceiling_passes(base_context: SecurityContext):
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": "Alice"})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_allowed


def test_rule_3_risk_level_exceeding_ceiling_denied(base_context: SecurityContext):
    # Lower agent ceiling to LOW, try to call calculate_refund (MEDIUM)
    low_risk_context = SecurityContext(
        agent_id=base_context.agent_id,
        project_id=base_context.project_id,
        assigned_tools={"calculate_refund"},
        agent_risk_ceiling=RiskLevel.LOW,
        tool_risk_levels={"calculate_refund": RiskLevel.MEDIUM},
        policy_rules={},
    )
    proposal = ToolProposal(tool_name="calculate_refund", arguments={"order_id": "ORD-1"})
    decision = PolicyEngine.evaluate(proposal, low_risk_context)
    assert decision.is_denied
    assert decision.rule_responsible == "risk_level_ceiling_rule"
    assert "exceeds agent risk ceiling" in decision.reason


# =============================================================================
# 4. RESOURCE OWNERSHIP RULE TESTS
# =============================================================================

def test_rule_4_same_tenant_resource_passes(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "Alice", "tenant_id": "proj-tenant-100"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_allowed


def test_rule_4_cross_tenant_spoofed_id_denied(base_context: SecurityContext):
    # Attacker attempts cross-tenant query
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "Alice", "tenant_id": "malicious-tenant-999"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "resource_ownership_rule"
    assert "Cross-tenant access violation" in decision.reason


def test_rule_4_unauthorized_uri_scope_denied(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "Alice", "resource_uri": "foreign-org-888/customer/123"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "resource_ownership_rule"


# =============================================================================
# 5. ARGUMENT CONSTRAINT RULE TESTS
# =============================================================================

def test_rule_5_missing_required_argument_denied(base_context: SecurityContext):
    # search_customer requires 'query'
    proposal = ToolProposal(tool_name="search_customer", arguments={})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_constraint_rule"
    assert "Missing or empty required argument" in decision.reason


def test_rule_5_empty_required_argument_denied(base_context: SecurityContext):
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": ""})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_constraint_rule"


def test_rule_5_oversized_payload_denied(base_context: SecurityContext):
    # Max argument size is 1000 bytes
    huge_query = "A" * 2000
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": huge_query})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_constraint_rule"
    assert "exceeds limit" in decision.reason


def test_rule_5_oversized_array_denied(base_context: SecurityContext):
    # Max array size is 10
    large_list = list(range(50))
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": "test", "filters": large_list})
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_constraint_rule"
    assert "array" in decision.reason


# =============================================================================
# 6. ARGUMENT PATTERN RULE TESTS
# =============================================================================

def test_rule_6_sql_injection_pattern_denied(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "admin' OR 1=1; DROP TABLE customers; --"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_pattern_rule"


def test_rule_6_path_traversal_pattern_denied(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "../../../etc/passwd"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_pattern_rule"


def test_rule_6_shell_injection_pattern_denied(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "; rm -rf / ;"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_pattern_rule"


def test_rule_6_custom_policy_pattern_denied(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="search_customer",
        arguments={"query": "Alice", "flags": "admin_override=true"},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.is_denied
    assert decision.rule_responsible == "argument_pattern_rule"


# =============================================================================
# 7. APPROVAL REQUIRED RULE TESTS
# =============================================================================

def test_rule_7_financial_tool_requires_approval(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="issue_refund",
        arguments={"order_id": "ORD-9001", "amount": 250.00},
    )
    decision = PolicyEngine.evaluate(proposal, base_context)
    assert decision.requires_approval
    assert decision.decision == PolicyDecisionOutcome.REQUIRES_APPROVAL
    assert decision.rule_responsible == "approval_required_rule"
    assert "requires explicit human approval" in decision.reason


# =============================================================================
# 8. FAIL-CLOSED BEHAVIOR TESTS
# =============================================================================

def test_fail_closed_on_none_context():
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": "test"})
    decision = PolicyEngine.evaluate(proposal, None)  # type: ignore
    assert decision.is_denied
    assert decision.rule_responsible == "fail_closed"


def test_fail_closed_on_none_proposal(base_context: SecurityContext):
    decision = PolicyEngine.evaluate(None, base_context)  # type: ignore
    assert decision.is_denied
    assert decision.rule_responsible == "input_validation"


# =============================================================================
# 9. GUARDED TOOL EXECUTOR INTEGRATION TESTS
# =============================================================================

def test_guarded_executor_blocks_unwhitelisted_tool(base_context: SecurityContext):
    proposal = ToolProposal(tool_name="arbitrary_bash_command", arguments={"cmd": "whoami"})
    res = GuardedToolExecutor.execute(proposal, base_context)
    assert res.is_blocked is True
    assert res.decision.is_denied
    assert res.result_data is None


def test_guarded_executor_allows_and_executes_safe_tool(base_context: SecurityContext):
    proposal = ToolProposal(tool_name="search_customer", arguments={"query": "Alice"})
    res = GuardedToolExecutor.execute(proposal, base_context)
    assert res.is_blocked is False
    assert res.decision.is_allowed
    assert res.result_data is not None
    assert "customers" in res.result_data
    assert len(res.result_data["customers"]) >= 1


def test_guarded_executor_suspends_for_approval(base_context: SecurityContext):
    proposal = ToolProposal(
        tool_name="issue_refund",
        arguments={"order_id": "ORD-9001", "amount": 100.00},
    )
    res = GuardedToolExecutor.execute(proposal, base_context)
    assert res.is_blocked is False
    assert res.requires_approval is True
    assert res.result_data is None
    assert res.decision.requires_approval is True
