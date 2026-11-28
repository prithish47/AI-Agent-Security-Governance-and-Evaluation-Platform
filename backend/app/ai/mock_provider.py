# =============================================================================
# AgentGuard — Deterministic Mock AI Provider
# =============================================================================
# ESSENTIAL TESTING COMPONENT:
# Allows deterministic scenarios without requiring paid external API keys.
# Supports scenarios for:
# - Legitimate tool calls and multi-step tasks
# - Unauthorized and unassigned tool calls
# - Explicitly denied tool calls
# - High-risk financial operations requiring approval
# - Prompt injection simulations
# - Infinite loop / iteration exhaustion simulations
# =============================================================================

from typing import Any, Dict, List
from app.ai.base import AIProvider, AIResponse, ToolCallProposal


class MockAIProvider(AIProvider):
    """
    Deterministic mock provider simulating realistic LLM agent tool-use patterns.
    """

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        prompt_lower = user_prompt.lower()
        step_count = len(conversation_history)

        # 1. SCENARIO: Malformed model response simulation
        if "simulate_malformed" in prompt_lower:
            return AIResponse(error="Simulated model parse failure: unparseable JSON")

        # 2. SCENARIO: Repeated tool call / Infinite loop simulation (Iteration exhaustion)
        if "simulate_infinite_loop" in prompt_lower or "loop_forever" in prompt_lower:
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="search_customer",
                    arguments={"query": f"loop_step_{step_count}"},
                )
            )

        # 3. SCENARIO: Prompt Injection / Unauthorized tool call
        if "delete_database" in prompt_lower or "drop table" in prompt_lower:
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="delete_database",
                    arguments={"action": "drop_all_tables"},
                )
            )

        # 4. SCENARIO: Cross-tenant data exfiltration attack
        if "cross_tenant" in prompt_lower or "foreign_tenant" in prompt_lower:
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="search_customer",
                    arguments={"query": "Alice", "tenant_id": "foreign-tenant-999"},
                )
            )

        # 5. SCENARIO: High-risk financial operation requiring approval
        if "refund" in prompt_lower:
            # If refund was already executed or approved in history, give final answer
            for msg in reversed(conversation_history):
                if msg.get("role") == "tool" and msg.get("tool_name") == "issue_refund":
                    amount = msg.get("result", {}).get("refunded_amount", 0)
                    return AIResponse(
                        final_answer=f"The refund of ${float(amount):.2f} has been processed successfully."
                    )
            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="issue_refund",
                    arguments={"order_id": "ORD-9001", "amount": 250.00},
                )
            )

        # 6. SCENARIO: Legitimate multi-step support inquiry
        # Step 1: Search customer
        # Step 2: Get support ticket
        # Step 3: Return final resolution
        if "support ticket" in prompt_lower or "multi-step" in prompt_lower or "check ticket" in prompt_lower:
            # Check if customer search was already completed
            has_searched = any(m.get("tool_name") == "search_customer" for m in conversation_history)
            has_ticket = any(m.get("tool_name") == "get_support_ticket" for m in conversation_history)

            if not has_searched:
                return AIResponse(
                    tool_call=ToolCallProposal(
                        tool_name="search_customer",
                        arguments={"query": "Alice Johnson"},
                    )
                )
            elif not has_ticket:
                return AIResponse(
                    tool_call=ToolCallProposal(
                        tool_name="get_support_ticket",
                        arguments={"ticket_id": "TKT-5001"},
                    )
                )
            else:
                return AIResponse(
                    final_answer="Customer Alice Johnson has ticket TKT-5001 regarding payment gateway timeout. The ticket priority is HIGH and status is OPEN."
                )

        # 7. SCENARIO: Legitimate customer search
        if "search" in prompt_lower or "customer" in prompt_lower or "find" in prompt_lower:
            # Check if already searched
            for msg in reversed(conversation_history):
                if msg.get("role") == "tool" and msg.get("tool_name") == "search_customer":
                    custs = msg.get("result", {}).get("customers", [])
                    count = len(custs)
                    return AIResponse(
                        final_answer=f"I found {count} customer(s) matching your search query."
                    )

            return AIResponse(
                tool_call=ToolCallProposal(
                    tool_name="search_customer",
                    arguments={"query": "Alice"},
                )
            )

        # 8. Default: Direct conversational answer
        return AIResponse(
            final_answer=f"AgentGuard simulated agent response to task: '{user_prompt}'."
        )
