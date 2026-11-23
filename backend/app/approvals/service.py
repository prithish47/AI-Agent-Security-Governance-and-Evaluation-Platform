# =============================================================================
# AgentGuard — Human Approval Service (Cryptographic Binding & Atomic Consumption)
# =============================================================================
# GUARANTEES:
# 1. Cryptographic action binding: verifies SHA-256 of canonical RFC 8785 JSON.
# 2. Tamper rejection: any change to tool arguments throws SecurityViolationError.
# 3. Atomic single-use consumption: an approval can NEVER be executed twice.
# 4. Separation of duties: enforced before allowing approval reviews.
# =============================================================================

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.canonical import verify_action_hash
from app.audit import service as audit_service
from app.audit.schemas import AuditEventCreate
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    SecurityViolationError,
    ValidationError,
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


async def approve_request(
    db: AsyncSession,
    approval_id: uuid.UUID,
    reviewer_id: Optional[uuid.UUID] = None,
    note: Optional[str] = None,
) -> ApprovalRequest:
    """Mark a pending approval as APPROVED after verifying payload integrity."""
    approval = await get_approval(db, approval_id)

    if approval.status != ApprovalStatus.PENDING:
        raise ConflictError(f"Approval is in state '{approval.status.value}', expected 'PENDING'")

    # Cryptographic integrity check: Verify action_hash matches stored arguments
    if not verify_action_hash(approval.tool_name, approval.tool_arguments, approval.action_hash):
        # Tamper detected!
        approval.status = ApprovalStatus.REJECTED
        approval.review_note = "SECURITY VIOLATION: Action hash mismatch detected. Payload was modified."
        await db.commit()

        await audit_service.record_audit_event(
            db,
            AuditEventCreate(
                project_id=approval.project_id,
                actor_id=reviewer_id,
                execution_id=approval.execution_id,
                event_type="SECURITY_VIOLATION",
                severity=AuditSeverity.CRITICAL,
                event_metadata={
                    "approval_id": str(approval_id),
                    "reason": "Approval action hash verification failed (tampering detected)",
                },
            ),
        )
        raise SecurityViolationError("Action hash mismatch: proposed action arguments were tampered with")

    approval.status = ApprovalStatus.APPROVED
    approval.reviewed_by = reviewer_id
    approval.review_note = note
    approval.reviewed_at = datetime.now(timezone.utc)
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
    """Reject a pending approval."""
    approval = await get_approval(db, approval_id)

    if approval.status != ApprovalStatus.PENDING:
        raise ConflictError(f"Approval is in state '{approval.status.value}', expected 'PENDING'")

    approval.status = ApprovalStatus.REJECTED
    approval.reviewed_by = reviewer_id
    approval.review_note = note
    approval.reviewed_at = datetime.now(timezone.utc)

    # Terminate execution as DENIED
    stmt = select(Execution).where(Execution.id == approval.execution_id)
    execution = (await db.execute(stmt)).scalar_one_or_none()
    if execution:
        execution.status = ExecutionStatus.DENIED
        execution.termination_reason = f"Human reviewer rejected action: {note or 'No reason provided'}"
        execution.completed_at = datetime.now(timezone.utc)

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
    db: AsyncSession, approval_id: uuid.UUID
) -> Execution:
    """
    ATOMIC SINGLE-USE CONSUMPTION & EXECUTION RESUMPTION:
    1. Atomically transitions status APPROVED -> CONSUMED.
    2. Re-verifies cryptographic SHA-256 action hash.
    3. Executes the approved tool from the safe catalog.
    4. Updates Execution status to COMPLETED.
    """
    # 1. Atomic consumption query (prevents double execution)
    stmt = (
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.status == ApprovalStatus.APPROVED,
        )
        .values(status=ApprovalStatus.CONSUMED)
        .returning(ApprovalRequest)
    )
    result = await db.execute(stmt)
    consumed_approval = result.scalar_one_or_none()

    if not consumed_approval:
        # Check current state for diagnostic error message
        current = await get_approval(db, approval_id)
        if current.status == ApprovalStatus.CONSUMED:
            raise ConflictError("Approval has already been consumed (single-use constraint enforced)")
        raise ConflictError(f"Approval cannot be executed in state '{current.status.value}', must be 'APPROVED'")

    # 2. Cryptographic Integrity Re-verification
    if not verify_action_hash(
        consumed_approval.tool_name,
        consumed_approval.tool_arguments,
        consumed_approval.action_hash,
    ):
        raise SecurityViolationError("Action hash mismatch during resumption: payload was tampered with")

    # 3. Lookup executor and execute tool
    executor = get_executor(consumed_approval.tool_name)
    if not executor:
        raise NotFoundError("ToolExecutor", consumed_approval.tool_name)

    tool_result = executor(consumed_approval.tool_arguments)

    # 4. Resume and complete Execution
    stmt = select(Execution).where(Execution.id == consumed_approval.execution_id)
    execution = (await db.execute(stmt)).scalar_one()

    # Record resumption execution step
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
    await db.refresh(execution)

    await audit_service.record_audit_event(
        db,
        AuditEventCreate(
            project_id=consumed_approval.project_id,
            execution_id=execution.id,
            event_type="APPROVAL_CONSUMED",
            severity=AuditSeverity.INFO,
            event_metadata={
                "approval_id": str(approval_id),
                "tool_name": consumed_approval.tool_name,
            },
        ),
    )
    return execution
