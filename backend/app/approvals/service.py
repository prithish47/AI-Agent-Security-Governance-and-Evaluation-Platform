# =============================================================================
# AgentGuard — Human Approval Service (Cryptographic Binding & Atomic Consumption)
# =============================================================================
# GUARANTEES:
# 1. Full execution-context cryptographic binding (RFC 8785 JCS + SHA-256).
# 2. Tamper & context-mismatch rejection -> SecurityViolationError + audit.
# 3. Expiration enforcement (expired approvals transition to EXPIRED and fail).
# 4. Atomic single-use consumption: an approval can NEVER be executed twice.
# 5. Separation of duties: execution initiator cannot approve, reject, or resume.
# =============================================================================

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.canonical import verify_action_hash
from app.audit import service as audit_service
from app.audit.schemas import AuditEventCreate
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    SecurityViolationError,
)
from app.persistence.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditSeverity,
    Execution,
    ExecutionStep,
    ExecutionStatus,
)
from app.tools.catalog import get_executor


async def get_approval(db: AsyncSession, approval_id: uuid.UUID) -> ApprovalRequest:
    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    approval = (await db.execute(stmt)).scalar_one_or_none()
    if not approval:
        raise NotFoundError("ApprovalRequest", str(approval_id))
    return approval


async def list_project_approvals(
    db: AsyncSession, project_id: uuid.UUID, status: Optional[ApprovalStatus] = None
) -> List[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(ApprovalRequest.project_id == project_id)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    stmt = stmt.order_by(ApprovalRequest.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _normalize_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def _enforce_separation_of_duties(
    db: AsyncSession,
    approval: ApprovalRequest,
    actor_id: Optional[uuid.UUID],
    action: str,
) -> Optional[Execution]:
    """
    Prevent an execution initiator from approving, rejecting, or resuming their own action.
    Returns the associated Execution record if found.
    """
    exec_stmt = select(Execution).where(Execution.id == approval.execution_id)
    execution = (await db.execute(exec_stmt)).scalar_one_or_none()
    if execution and execution.user_id and actor_id and execution.user_id == actor_id:
        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=approval.project_id,
                actor_id=actor_id,
                execution_id=approval.execution_id,
                event_type="APPROVAL_SELF_REVIEW_BLOCKED",
                severity=AuditSeverity.WARNING,
                event_metadata={
                    "approval_id": str(approval.id),
                    "action": action,
                    "reason": f"Initiator attempted to {action} their own execution action",
                },
            ),
        )
        raise ForbiddenError(
            f"Separation of duties violation: execution initiator cannot {action} their own action"
        )
    return execution


async def _check_not_expired(
    db: AsyncSession,
    approval: ApprovalRequest,
    actor_id: Optional[uuid.UUID],
) -> datetime:
    """Ensure approval has not passed expires_at; mark EXPIRED and fail if it has."""
    now = datetime.now(timezone.utc)
    if approval.expires_at is not None and _normalize_utc(approval.expires_at) <= now:
        approval.status = ApprovalStatus.EXPIRED
        await db.commit()
        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=approval.project_id,
                actor_id=actor_id,
                execution_id=approval.execution_id,
                event_type="APPROVAL_EXPIRED",
                severity=AuditSeverity.WARNING,
                event_metadata={"approval_id": str(approval.id)},
            ),
        )
        raise ConflictError("Approval request has expired")
    return now


async def _verify_approval_binding_and_context(
    db: AsyncSession,
    approval: ApprovalRequest,
    execution: Optional[Execution],
    actor_id: Optional[uuid.UUID],
    stage: str,
) -> None:
    """
    Verify execution/project/agent/policy context consistency AND recompute
    the RFC 8785 SHA-256 action hash against the stored hash.
    Marks approval REJECTED and raises SecurityViolationError on any mismatch.
    """
    violation_reason: Optional[str] = None

    if not execution:
        violation_reason = "Associated execution record is missing"
    elif execution.project_id != approval.project_id:
        violation_reason = "Approval project_id does not match execution project_id"
    elif execution.agent_id != approval.agent_id:
        violation_reason = "Approval agent_id does not match execution agent_id"
    elif execution.status != ExecutionStatus.REQUIRES_APPROVAL:
        violation_reason = (
            f"Execution is in state '{execution.status.value}', expected 'REQUIRES_APPROVAL'"
        )
    else:
        snap = execution.context_snapshot or {}
        if snap.get("policy_version") != approval.policy_version:
            violation_reason = (
                f"Policy version mismatch: approval bound to v{approval.policy_version}, "
                f"execution snapshot has v{snap.get('policy_version')}"
            )
        elif snap.get("agent_risk_ceiling") != approval.agent_risk_ceiling:
            violation_reason = (
                f"Risk ceiling mismatch: approval bound to '{approval.agent_risk_ceiling}', "
                f"execution snapshot has '{snap.get('agent_risk_ceiling')}'"
            )

    if violation_reason is None and not verify_action_hash(
        project_id=approval.project_id,
        agent_id=approval.agent_id,
        execution_id=approval.execution_id,
        tool_name=approval.tool_name,
        arguments=approval.tool_arguments,
        policy_version=approval.policy_version,
        agent_risk_ceiling=approval.agent_risk_ceiling,
        expected_hash=approval.action_hash,
    ):
        violation_reason = "Approval action hash verification failed (tampering or context drift detected)"

    if violation_reason is not None:
        approval.status = ApprovalStatus.REJECTED
        approval.review_note = f"SECURITY VIOLATION ({stage}): {violation_reason}"
        await db.commit()

        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=approval.project_id,
                actor_id=actor_id,
                execution_id=approval.execution_id,
                event_type="SECURITY_VIOLATION",
                severity=AuditSeverity.CRITICAL,
                event_metadata={
                    "approval_id": str(approval.id),
                    "stage": stage,
                    "reason": violation_reason,
                },
            ),
        )
        raise SecurityViolationError(violation_reason)


async def approve_request(
    db: AsyncSession,
    approval_id: uuid.UUID,
    reviewer_id: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> ApprovalRequest:
    """Mark a pending approval as APPROVED after verifying payload & context integrity."""
    approval = await get_approval(db, approval_id)

    if approval.status != ApprovalStatus.PENDING:
        raise ConflictError(f"Approval is in state '{approval.status.value}', expected 'PENDING'")

    now = await _check_not_expired(db, approval, reviewer_id)
    execution = await _enforce_separation_of_duties(db, approval, reviewer_id, "approve")
    await _verify_approval_binding_and_context(db, approval, execution, reviewer_id, "approve")

    approval.status = ApprovalStatus.APPROVED
    approval.reviewed_by = reviewer_id
    approval.review_note = note
    approval.reviewed_at = now
    await db.commit()
    await db.refresh(approval)

    await audit_service.record_audit_event(
        db,
        AuditEventCreate(
            project_id=approval.project_id,
            actor_id=reviewer_id,
            execution_id=approval.execution_id,
            event_type="APPROVAL_APPROVED",
            severity=AuditSeverity.INFO,
            event_metadata={"approval_id": str(approval_id), "note": note},
        ),
    )
    return approval


async def reject_request(
    db: AsyncSession,
    approval_id: uuid.UUID,
    reviewer_id: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> ApprovalRequest:
    """Reject a pending approval and terminate its suspended execution."""
    approval = await get_approval(db, approval_id)

    if approval.status != ApprovalStatus.PENDING:
        raise ConflictError(f"Approval is in state '{approval.status.value}', expected 'PENDING'")

    now = await _check_not_expired(db, approval, reviewer_id)
    execution = await _enforce_separation_of_duties(db, approval, reviewer_id, "reject")

    approval.status = ApprovalStatus.REJECTED
    approval.reviewed_by = reviewer_id
    approval.review_note = note
    approval.reviewed_at = now

    if execution:
        execution.status = ExecutionStatus.DENIED
        execution.termination_reason = f"Human reviewer rejected action: {note or 'No reason provided'}"
        execution.completed_at = now

    await db.commit()
    await db.refresh(approval)

    await audit_service.record_audit_event(
        db,
        AuditEventCreate(
            project_id=approval.project_id,
            actor_id=reviewer_id,
            execution_id=approval.execution_id,
            event_type="APPROVAL_REJECTED",
            severity=AuditSeverity.WARNING,
            event_metadata={"approval_id": str(approval_id), "note": note},
        ),
    )
    return approval


async def resume_and_consume_approval(
    db: AsyncSession,
    approval_id: uuid.UUID,
    actor_id: Optional[uuid.UUID] = None,
) -> Execution:
    """
    EXECUTION INTEGRITY & ATOMIC SINGLE-USE CONSUMPTION:
    1. Retrieve approval and enforce separation of duties.
    2. Verify status is APPROVED and not expired.
    3. Reconstruct action binding, recompute RFC 8785 SHA-256 hash, and verify
       execution, agent, project, tool, and policy context BEFORE consumption.
    4. Atomically transition APPROVED -> CONSUMED (with expiration guard).
    5. Execute strictly the verified approved tool_name and tool_arguments.
    6. Record step trace and complete Execution.
    """
    pre_approval = await get_approval(db, approval_id)

    if pre_approval.status != ApprovalStatus.APPROVED:
        if pre_approval.status == ApprovalStatus.CONSUMED:
            raise ConflictError("Approval has already been consumed (single-use constraint enforced)")
        raise ConflictError(
            f"Approval cannot be executed in state '{pre_approval.status.value}', must be 'APPROVED'"
        )

    execution = await _enforce_separation_of_duties(db, pre_approval, actor_id, "resume")
    now = await _check_not_expired(db, pre_approval, actor_id)
    await _verify_approval_binding_and_context(db, pre_approval, execution, actor_id, "resume")

    # Atomic single-use consumption guard (prevents concurrent double execution)
    stmt = (
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.status == ApprovalStatus.APPROVED,
            or_(ApprovalRequest.expires_at.is_(None), ApprovalRequest.expires_at > now),
        )
        .values(status=ApprovalStatus.CONSUMED)
        .returning(ApprovalRequest)
        .execution_options(synchronize_session=False)
    )
    result = await db.execute(stmt)
    consumed_approval = result.scalar_one_or_none()

    if not consumed_approval:
        current = await get_approval(db, approval_id)
        if current.status == ApprovalStatus.CONSUMED:
            raise ConflictError("Approval has already been consumed (single-use constraint enforced)")
        raise ConflictError(
            f"Approval cannot be executed in state '{current.status.value}', must be 'APPROVED'"
        )

    # Execute strictly the verified approved action from the safe catalog
    executor = get_executor(consumed_approval.tool_name)
    if not executor:
        raise NotFoundError("ToolExecutor", consumed_approval.tool_name)

    tool_result = executor(consumed_approval.tool_arguments)

    assert execution is not None
    step_num = execution.iteration_count + 1
    step = ExecutionStep(
        execution_id=execution.id,
        step_number=step_num,
        step_type="APPROVED_TOOL_EXECUTION",
        tool_name=consumed_approval.tool_name,
        tool_arguments=consumed_approval.tool_arguments,
        policy_decision="APPROVED_AND_EXECUTED",
        tool_result=tool_result,
        model_response=f"Approved action '{consumed_approval.tool_name}' executed successfully.",
    )
    db.add(step)

    execution.status = ExecutionStatus.COMPLETED
    execution.final_response = (
        f"Approved tool '{consumed_approval.tool_name}' was executed successfully. Result: {tool_result}"
    )
    execution.termination_reason = "COMPLETED"
    execution.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(consumed_approval)
    await db.refresh(execution)

    await audit_service.record_audit_event(
        db,
        AuditEventCreate(
            project_id=consumed_approval.project_id,
            actor_id=actor_id,
            execution_id=execution.id,
            event_type="APPROVAL_CONSUMED",
            severity=AuditSeverity.INFO,
            event_metadata={
                "approval_id": str(approval_id),
                "tool_name": consumed_approval.tool_name,
                "policy_version": consumed_approval.policy_version,
            },
        ),
    )
    return execution
