# =============================================================================
# AgentGuard — Agent Runtime Orchestrator
# =============================================================================
# Coordinates:
# 1. Loading agent config and pinning immutable execution context
# 2. Bounded execution loop: min(agent.max_iterations, global_iteration_ceiling=20)
# 3. AI provider invocation
# 4. Mandatory Guarded Tool Executor interception (no model bypasses security)
# 5. Policy decision handling (ALLOW, DENY, REQUIRES_APPROVAL)
# 6. Suspending execution when human approval is required
# 7. Complete step-by-step execution trace recording
# =============================================================================

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.approvals.canonical import compute_action_hash
from app.audit import service as audit_service
from app.audit.schemas import AuditEventCreate
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.persistence.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditSeverity,
    Execution,
    ExecutionStep,
    ExecutionStatus,
)
from app.policies.domain import ToolProposal
from app.runtime.context import create_pinned_context
from app.tools.guarded_executor import GuardedToolExecutor


class AgentRuntimeOrchestrator:
    """
    Controlled execution loop orchestrator.
    """

    @classmethod
    async def execute_task(
        cls,
        db: AsyncSession,
        agent_id: uuid.UUID,
        task_prompt: str,
        user_id: Optional[uuid.UUID] = None,
        provider: Optional[AIProvider] = None,
    ) -> Execution:
        """
        Orchestrate agent execution with pinned context and bounded iteration limits.
        """
        # 1. Construct pinned immutable execution context snapshot
        security_context, agent = await create_pinned_context(db, agent_id)

        # 2. Select AI Provider (defaults to MockAIProvider if not specified)
        if provider is None:
            provider = MockAIProvider()

        # 3. Create active Execution database record
        execution = Execution(
            project_id=agent.project_id,
            agent_id=agent.id,
            user_id=user_id,
            task_prompt=task_prompt,
            status=ExecutionStatus.RUNNING,
            iteration_count=0,
            context_snapshot={
                "agent_name": agent.name,
                "agent_risk_ceiling": security_context.agent_risk_ceiling.value,
                "assigned_tools": list(security_context.assigned_tools),
                "policy_version": security_context.policy_version_number,
                "policy_rules": security_context.policy_rules,
            },
            started_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        await db.flush()

        # Record audit event: EXECUTION_STARTED
        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=agent.project_id,
                actor_id=user_id,
                execution_id=execution.id,
                event_type="EXECUTION_STARTED",
                severity=AuditSeverity.INFO,
                event_metadata={"agent_id": str(agent.id), "task": task_prompt},
            ),
        )

        # 4. Determine bounded iteration ceiling
        iteration_limit = min(agent.max_iterations, settings.global_iteration_ceiling)

        conversation_history: List[Dict[str, Any]] = []
        step_number = 0
        iteration = 0

        available_tools_list = [
            {"name": t_name, "schema": security_context.tool_schemas.get(t_name, {})}
            for t_name in security_context.assigned_tools
        ]

        # 5. Controlled Execution Loop
        while iteration < iteration_limit:
            iteration += 1
            execution.iteration_count = iteration

            # Query AI Model Adapter
            ai_response = await provider.generate(
                system_prompt=agent.system_prompt,
                user_prompt=task_prompt,
                conversation_history=conversation_history,
                available_tools=available_tools_list,
            )

            # Check Model Error
            if ai_response.is_error:
                step_number += 1
                step = ExecutionStep(
                    execution_id=execution.id,
                    step_number=step_number,
                    step_type="ERROR",
                    model_response=ai_response.error,
                )
                db.add(step)

                execution.status = ExecutionStatus.MODEL_ERROR
                execution.termination_reason = ai_response.error
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return execution

            # Check Final Answer
            if ai_response.has_final_answer:
                step_number += 1
                step = ExecutionStep(
                    execution_id=execution.id,
                    step_number=step_number,
                    step_type="FINAL_ANSWER",
                    model_response=ai_response.final_answer,
                )
                db.add(step)

                execution.status = ExecutionStatus.COMPLETED
                execution.final_response = ai_response.final_answer
                execution.termination_reason = "COMPLETED"
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()

                # Audit event: EXECUTION_COMPLETED
                await audit_service.record_audit_event(
                    db,
                    AuditEventCreate(
                        project_id=agent.project_id,
                        actor_id=user_id,
                        execution_id=execution.id,
                        event_type="EXECUTION_COMPLETED",
                        severity=AuditSeverity.INFO,
                        event_metadata={"iteration_count": iteration},
                    ),
                )
                return execution

            # Handle Tool Call Proposal
            if ai_response.has_tool_call and ai_response.tool_call:
                proposal_data = ai_response.tool_call
                step_number += 1

                # Send proposal through GUARDED TOOL EXECUTOR
                proposal = ToolProposal(
                    tool_name=proposal_data.tool_name,
                    arguments=proposal_data.arguments,
                )
                guarded_result = GuardedToolExecutor.execute(proposal, security_context)

                # Persist execution step trace
                step = ExecutionStep(
                    execution_id=execution.id,
                    step_number=step_number,
                    step_type="TOOL_CALL",
                    tool_name=proposal.tool_name,
                    tool_arguments=proposal.arguments,
                    policy_decision=guarded_result.decision.decision.value,
                    policy_rule=guarded_result.decision.rule_responsible,
                    policy_reason=guarded_result.decision.reason,
                    tool_result=guarded_result.result_data,
                    policy_eval_ms=guarded_result.decision.evaluation_latency_ms,
                )
                db.add(step)

                # Case A: Policy DENY
                if guarded_result.is_blocked:
                    execution.status = ExecutionStatus.DENIED
                    execution.termination_reason = f"Denied by rule: {guarded_result.decision.rule_responsible}"
                    execution.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    await audit_service.record_audit_event(
                        db,
                        AuditEventCreate(
                            project_id=agent.project_id,
                            actor_id=user_id,
                            execution_id=execution.id,
                            event_type="TOOL_DENIED",
                            severity=AuditSeverity.WARNING,
                            event_metadata={
                                "tool_name": proposal.tool_name,
                                "rule": guarded_result.decision.rule_responsible,
                                "reason": guarded_result.decision.reason,
                            },
                        ),
                    )
                    return execution

                # Case B: Policy REQUIRES_APPROVAL
                if guarded_result.requires_approval:
                    # Suspend execution and create pending approval record with full RFC 8785 action binding
                    now_utc = datetime.now(timezone.utc)
                    action_hash = compute_action_hash(
                        project_id=agent.project_id,
                        agent_id=agent.id,
                        execution_id=execution.id,
                        tool_name=proposal.tool_name,
                        arguments=proposal.arguments,
                        policy_version=security_context.policy_version_number,
                        agent_risk_ceiling=security_context.agent_risk_ceiling.value,
                    )
                    approval = ApprovalRequest(
                        project_id=agent.project_id,
                        execution_id=execution.id,
                        agent_id=agent.id,
                        tool_name=proposal.tool_name,
                        tool_arguments=proposal.arguments,
                        policy_version=security_context.policy_version_number,
                        agent_risk_ceiling=security_context.agent_risk_ceiling.value,
                        action_hash=action_hash,
                        status=ApprovalStatus.PENDING,
                        expires_at=now_utc + timedelta(minutes=settings.approval_expiration_minutes),
                    )
                    db.add(approval)

                    execution.status = ExecutionStatus.REQUIRES_APPROVAL
                    execution.termination_reason = f"Awaiting human approval for tool '{proposal.tool_name}'"
                    await db.commit()

                    await audit_service.record_audit_event(
                        db,
                        AuditEventCreate(
                            project_id=agent.project_id,
                            actor_id=user_id,
                            execution_id=execution.id,
                            event_type="APPROVAL_REQUESTED",
                            severity=AuditSeverity.WARNING,
                            event_metadata={
                                "tool_name": proposal.tool_name,
                                "action_hash": action_hash,
                            },
                        ),
                    )
                    return execution

                # Case C: Policy ALLOW (Tool Executed)
                await audit_service.record_audit_event(
                    db,
                    AuditEventCreate(
                        project_id=agent.project_id,
                        actor_id=user_id,
                        execution_id=execution.id,
                        event_type="TOOL_ALLOWED",
                        severity=AuditSeverity.INFO,
                        event_metadata={
                            "tool_name": proposal.tool_name,
                            "latency_ms": guarded_result.decision.evaluation_latency_ms,
                        },
                    ),
                )

                # Feed result back into conversation history for the next model turn
                conversation_history.append({
                    "role": "assistant",
                    "tool_call": proposal.tool_name,
                    "arguments": proposal.arguments,
                })
                conversation_history.append({
                    "role": "tool",
                    "tool_name": proposal.tool_name,
                    "result": guarded_result.result_data,
                })

        # 6. Iteration Ceiling Reached
        execution.status = ExecutionStatus.MAX_ITERATIONS_REACHED
        execution.termination_reason = f"Agent exceeded maximum permitted iteration limit of {iteration_limit}"
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()

        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=agent.project_id,
                actor_id=user_id,
                execution_id=execution.id,
                event_type="MAX_ITERATIONS_REACHED",
                severity=AuditSeverity.WARNING,
                event_metadata={"limit": iteration_limit},
            ),
        )
        return execution
