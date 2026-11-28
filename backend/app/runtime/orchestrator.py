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
# 7. Resuming suspended execution securely after approval consumption
# 8. Complete step-by-step execution trace recording
# =============================================================================

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.approvals.canonical import compute_action_hash, compute_tool_schema_hash
from app.audit import service as audit_service
from app.audit.schemas import AuditEventCreate
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.persistence.models import (
    Agent,
    ApprovalRequest,
    ApprovalStatus,
    AuditSeverity,
    Execution,
    ExecutionStep,
    ExecutionStatus,
)
from app.policies.domain import SecurityContext, ToolProposal
from app.runtime.context import create_pinned_context, reconstruct_or_load_pinned_context
from app.runtime.state import validate_execution_transition
from app.tools.guarded_executor import GuardedToolExecutor


class AgentRuntimeOrchestrator:
    """
    Controlled execution loop orchestrator with multi-turn resumption support.
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
        Orchestrate initial agent execution with pinned context and bounded iteration limits.
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
            conversation_history=[],
            context_snapshot={
                "agent_name": agent.name,
                "agent_risk_ceiling": security_context.agent_risk_ceiling.value,
                "assigned_tools": list(security_context.assigned_tools),
                "policy_version": security_context.policy_version_number,
                "policy_id": str(agent.policy_id) if agent.policy_id else None,
                "policy_rules": security_context.policy_rules,
                "tool_schemas": security_context.tool_schemas,
                "tool_risk_levels": {k: v.value for k, v in security_context.tool_risk_levels.items()},
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

        iteration_limit = min(agent.max_iterations, settings.global_iteration_ceiling)

        return await cls._run_orchestration_loop(
            db=db,
            execution=execution,
            agent=agent,
            security_context=security_context,
            provider=provider,
            conversation_history=[],
            iteration=0,
            step_number=0,
            iteration_limit=iteration_limit,
            user_id=user_id,
        )

    @classmethod
    async def resume_execution(
        cls,
        db: AsyncSession,
        execution_id: uuid.UUID,
        consumed_approval: ApprovalRequest,
        provider: Optional[AIProvider] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Execution:
        """
        SECURE MULTI-TURN RESUMPTION:
        1. Verify execution is in REQUIRES_APPROVAL state.
        2. Reconstruct pinned SecurityContext from immutable snapshot.
        3. Transition status from REQUIRES_APPROVAL to RUNNING.
        4. Execute ONLY the approved tool and arguments via GuardedToolExecutor.
        5. Record step trace and feed tool result into preserved conversation history.
        6. Resume the bounded orchestration loop up to min(agent.max_iterations, ceiling).
        """
        stmt_exec = select(Execution).where(Execution.id == execution_id)
        execution = (await db.execute(stmt_exec)).scalar_one_or_none()
        if not execution:
            raise NotFoundError("Execution", str(execution_id))

        if execution.status != ExecutionStatus.REQUIRES_APPROVAL:
            raise ConflictError(
                f"Cannot resume execution in state '{execution.status.value}', expected 'REQUIRES_APPROVAL'"
            )

        stmt_agent = select(Agent).where(Agent.id == execution.agent_id)
        agent = (await db.execute(stmt_agent)).scalar_one_or_none()
        if not agent:
            raise NotFoundError("Agent", str(execution.agent_id))

        # Reconstruct pinned SecurityContext
        security_context = await reconstruct_or_load_pinned_context(
            db, execution.context_snapshot or {}, agent.id, execution.project_id
        )

        if provider is None:
            provider = MockAIProvider()

        # Transition state: REQUIRES_APPROVAL -> RUNNING
        validate_execution_transition(execution.status, ExecutionStatus.RUNNING)
        execution.status = ExecutionStatus.RUNNING
        execution.termination_reason = None

        # Fetch existing steps count
        stmt_steps = (
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution.id)
            .order_by(ExecutionStep.step_number.asc())
        )
        existing_steps = list((await db.execute(stmt_steps)).scalars().all())
        step_number = max([s.step_number for s in existing_steps], default=0)

        # Retrieve preserved conversation history
        conversation_history: List[Dict[str, Any]] = list(execution.conversation_history or [])
        if not conversation_history and existing_steps:
            # Reconstruct from step history if legacy snapshot lacked conversation_history
            for s in existing_steps:
                if s.step_type == "TOOL_CALL" and s.tool_result is not None:
                    conversation_history.append({
                        "role": "assistant",
                        "tool_call": s.tool_name,
                        "arguments": s.tool_arguments,
                    })
                    conversation_history.append({
                        "role": "tool",
                        "tool_name": s.tool_name,
                        "result": s.tool_result,
                    })

        # 4. Execute strictly the verified approved action via GuardedToolExecutor
        guarded_result = GuardedToolExecutor.execute_approved(
            tool_name=consumed_approval.tool_name,
            arguments=consumed_approval.tool_arguments,
            context=security_context,
        )

        step_number += 1

        # Check for tool execution failure post-approval
        if guarded_result.is_blocked:
            step = ExecutionStep(
                execution_id=execution.id,
                step_number=step_number,
                step_type="TOOL_ERROR",
                tool_name=consumed_approval.tool_name,
                tool_arguments=consumed_approval.tool_arguments,
                policy_decision="TOOL_EXECUTION_FAILED",
                policy_reason=guarded_result.error_message,
                tool_result={"error": guarded_result.error_message},
            )
            db.add(step)

            validate_execution_transition(execution.status, ExecutionStatus.TOOL_ERROR)
            execution.status = ExecutionStatus.TOOL_ERROR
            execution.termination_reason = f"Approved tool '{consumed_approval.tool_name}' failed: {guarded_result.error_message}"
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await audit_service.record_audit_event(
                db,
                AuditEventCreate(
                    project_id=execution.project_id,
                    actor_id=actor_id or execution.user_id,
                    execution_id=execution.id,
                    event_type="TOOL_ERROR",
                    severity=AuditSeverity.WARNING,
                    event_metadata={
                        "tool_name": consumed_approval.tool_name,
                        "error": guarded_result.error_message,
                    },
                ),
            )
            return execution

        # Record APPROVED_TOOL_EXECUTION step trace
        step = ExecutionStep(
            execution_id=execution.id,
            step_number=step_number,
            step_type="APPROVED_TOOL_EXECUTION",
            tool_name=consumed_approval.tool_name,
            tool_arguments=consumed_approval.tool_arguments,
            policy_decision="APPROVED_AND_EXECUTED",
            tool_result=guarded_result.result_data,
            model_response=f"Approved action '{consumed_approval.tool_name}' executed successfully.",
            policy_eval_ms=guarded_result.decision.evaluation_latency_ms if guarded_result.decision else 0.0,
        )
        db.add(step)

        # Feed tool result back into preserved conversation history
        conversation_history.append({
            "role": "assistant",
            "tool_call": consumed_approval.tool_name,
            "arguments": consumed_approval.tool_arguments,
        })
        conversation_history.append({
            "role": "tool",
            "tool_name": consumed_approval.tool_name,
            "result": guarded_result.result_data,
        })
        execution.conversation_history = list(conversation_history)
        await db.flush()

        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=execution.project_id,
                actor_id=actor_id or execution.user_id,
                execution_id=execution.id,
                event_type="TOOL_ALLOWED",
                severity=AuditSeverity.INFO,
                event_metadata={
                    "tool_name": consumed_approval.tool_name,
                    "resumed_from_approval": str(consumed_approval.id),
                },
            ),
        )

        iteration_limit = min(agent.max_iterations, settings.global_iteration_ceiling)

        # Resume the bounded orchestration loop starting from preserved iteration count
        return await cls._run_orchestration_loop(
            db=db,
            execution=execution,
            agent=agent,
            security_context=security_context,
            provider=provider,
            conversation_history=conversation_history,
            iteration=execution.iteration_count,
            step_number=step_number,
            iteration_limit=iteration_limit,
            user_id=actor_id or execution.user_id,
        )

    @classmethod
    async def _run_orchestration_loop(
        cls,
        db: AsyncSession,
        execution: Execution,
        agent: Agent,
        security_context: SecurityContext,
        provider: AIProvider,
        conversation_history: List[Dict[str, Any]],
        iteration: int,
        step_number: int,
        iteration_limit: int,
        user_id: Optional[uuid.UUID],
    ) -> Execution:
        """
        Shared bounded execution loop for initial task orchestration and resumption.
        """
        available_tools_list = [
            {"name": t_name, "schema": security_context.tool_schemas.get(t_name, {})}
            for t_name in security_context.assigned_tools
        ]

        while iteration < iteration_limit:
            iteration += 1
            execution.iteration_count = iteration

            # Query AI Model Adapter (resilient exception handling)
            try:
                ai_response = await provider.generate(
                    system_prompt=agent.system_prompt,
                    user_prompt=execution.task_prompt,
                    conversation_history=conversation_history,
                    available_tools=available_tools_list,
                )
            except Exception as exc:
                step_number += 1
                step = ExecutionStep(
                    execution_id=execution.id,
                    step_number=step_number,
                    step_type="ERROR",
                    model_response=f"Model provider exception: {str(exc)}",
                )
                db.add(step)

                validate_execution_transition(execution.status, ExecutionStatus.MODEL_ERROR)
                execution.status = ExecutionStatus.MODEL_ERROR
                execution.termination_reason = f"Model provider error: {str(exc)}"
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()

                await audit_service.record_audit_event(
                    db,
                    AuditEventCreate(
                        project_id=agent.project_id,
                        actor_id=user_id,
                        execution_id=execution.id,
                        event_type="EXECUTION_FAILED",
                        severity=AuditSeverity.WARNING,
                        event_metadata={"error": str(exc)},
                    ),
                )
                return execution

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

                validate_execution_transition(execution.status, ExecutionStatus.MODEL_ERROR)
                execution.status = ExecutionStatus.MODEL_ERROR
                execution.termination_reason = ai_response.error
                execution.completed_at = datetime.now(timezone.utc)
                await db.commit()

                await audit_service.record_audit_event(
                    db,
                    AuditEventCreate(
                        project_id=agent.project_id,
                        actor_id=user_id,
                        execution_id=execution.id,
                        event_type="EXECUTION_FAILED",
                        severity=AuditSeverity.WARNING,
                        event_metadata={"error": ai_response.error},
                    ),
                )
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

                validate_execution_transition(execution.status, ExecutionStatus.COMPLETED)
                execution.status = ExecutionStatus.COMPLETED
                execution.final_response = ai_response.final_answer
                execution.termination_reason = "COMPLETED"
                execution.completed_at = datetime.now(timezone.utc)
                execution.conversation_history = list(conversation_history)
                await db.commit()

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
                    validate_execution_transition(execution.status, ExecutionStatus.DENIED)
                    execution.status = ExecutionStatus.DENIED
                    execution.termination_reason = f"Denied by rule: {guarded_result.decision.rule_responsible}"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.conversation_history = list(conversation_history)
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
                    now_utc = datetime.now(timezone.utc)
                    b_ver = getattr(settings, "approval_binding_version", 1)
                    tool_schema = security_context.tool_schemas.get(proposal.tool_name, {})
                    tool_schema_hash = compute_tool_schema_hash(tool_schema)

                    action_hash = compute_action_hash(
                        project_id=agent.project_id,
                        agent_id=agent.id,
                        execution_id=execution.id,
                        tool_name=proposal.tool_name,
                        arguments=proposal.arguments,
                        policy_version=security_context.policy_version_number,
                        agent_risk_ceiling=security_context.agent_risk_ceiling.value,
                        binding_version=b_ver,
                        policy_id=security_context.policy_id,
                        tool_schema_hash=tool_schema_hash,
                    )

                    policy_uuid = uuid.UUID(security_context.policy_id) if security_context.policy_id else None

                    approval = ApprovalRequest(
                        project_id=agent.project_id,
                        execution_id=execution.id,
                        agent_id=agent.id,
                        tool_name=proposal.tool_name,
                        tool_arguments=proposal.arguments,
                        policy_version=security_context.policy_version_number,
                        agent_risk_ceiling=security_context.agent_risk_ceiling.value,
                        binding_version=b_ver,
                        policy_id=policy_uuid,
                        tool_schema_hash=tool_schema_hash,
                        action_hash=action_hash,
                        status=ApprovalStatus.PENDING,
                        expires_at=now_utc + timedelta(minutes=settings.approval_expiration_minutes),
                    )
                    db.add(approval)

                    validate_execution_transition(execution.status, ExecutionStatus.REQUIRES_APPROVAL)
                    execution.status = ExecutionStatus.REQUIRES_APPROVAL
                    execution.termination_reason = f"Awaiting human approval for tool '{proposal.tool_name}'"
                    execution.conversation_history = list(conversation_history)
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
                                "binding_version": 2,
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
                execution.conversation_history = list(conversation_history)

        # 6. Iteration Ceiling Reached
        validate_execution_transition(execution.status, ExecutionStatus.MAX_ITERATIONS_REACHED)
        execution.status = ExecutionStatus.MAX_ITERATIONS_REACHED
        execution.termination_reason = f"Agent exceeded maximum permitted iteration limit of {iteration_limit}"
        execution.completed_at = datetime.now(timezone.utc)
        execution.conversation_history = list(conversation_history)
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
