# =============================================================================
# AgentGuard — Approvals Endpoints
# =============================================================================

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approval_service
from app.approvals.schemas import ApprovalResponse, ApprovalReviewRequest
from app.auth.rbac import (
    Permission,
    get_authorized_resource,
    get_current_user,
    require_project_permission,
)
from app.core.database import get_db
from app.persistence.models import ApprovalRequest, ApprovalStatus, User
from app.runtime.schemas import ExecutionResponse

router = APIRouter(tags=["Human Approvals"])


@router.get("/projects/{project_id}/approvals", response_model=List[ApprovalResponse])
async def list_project_approvals(
    project_id: uuid.UUID,
    status: Optional[ApprovalStatus] = Query(None, description="Filter by approval status"),
    _: User = Depends(require_project_permission(Permission.VIEW_DASHBOARD)),
    db: AsyncSession = Depends(get_db),
):
    """List pending or reviewed approval requests for a project."""
    return await approval_service.list_project_approvals(db, project_id, status)


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get approval request details including canonical action hash."""
    return await get_authorized_resource(
        db, ApprovalRequest, approval_id, "ApprovalRequest", current_user, Permission.VIEW_DASHBOARD
    )


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_action(
    approval_id: uuid.UUID,
    review_in: ApprovalReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending high-risk action after verifying payload integrity and RBAC."""
    await get_authorized_resource(
        db, ApprovalRequest, approval_id, "ApprovalRequest", current_user, Permission.APPROVE_ACTIONS
    )
    return await approval_service.approve_request(
        db=db,
        approval_id=approval_id,
        reviewer_id=current_user.id,
        note=review_in.note,
    )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_action(
    approval_id: uuid.UUID,
    review_in: ApprovalReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending high-risk action (requires APPROVE_ACTIONS)."""
    await get_authorized_resource(
        db, ApprovalRequest, approval_id, "ApprovalRequest", current_user, Permission.APPROVE_ACTIONS
    )
    return await approval_service.reject_request(
        db=db,
        approval_id=approval_id,
        reviewer_id=current_user.id,
        note=review_in.note,
    )


@router.post("/approvals/{approval_id}/resume", response_model=ExecutionResponse)
async def resume_approved_action(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Atomically consume an approved request and resume execution.
    Single-use guarantee and APPROVE_ACTIONS RBAC enforced.
    """
    await get_authorized_resource(
        db, ApprovalRequest, approval_id, "ApprovalRequest", current_user, Permission.APPROVE_ACTIONS
    )
    return await approval_service.resume_and_consume_approval(
        db, approval_id, actor_id=current_user.id
    )
