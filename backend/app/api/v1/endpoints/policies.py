# =============================================================================
# AgentGuard — Security Policies Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import (
    Permission,
    get_authorized_resource,
    get_current_user,
    require_project_permission,
)
from app.core.database import get_db
from app.persistence.models import SecurityPolicy, User
from app.policies import service as policy_service
from app.policies.schemas import (
    PolicyCreate,
    PolicyResponse,
    PolicyVersionCreate,
    PolicyVersionResponse,
    PolicyActivateVersion,
)

router = APIRouter(tags=["Security Policies"])


@router.get("/projects/{project_id}/policies", response_model=List[PolicyResponse])
async def list_project_policies(
    project_id: uuid.UUID,
    _: User = Depends(require_project_permission(Permission.VIEW_DASHBOARD)),
    db: AsyncSession = Depends(get_db),
):
    """List all policies in a project."""
    return await policy_service.list_project_policies(db, project_id)


@router.post("/projects/{project_id}/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    project_id: uuid.UUID,
    policy_in: PolicyCreate,
    current_user: User = Depends(require_project_permission(Permission.MANAGE_POLICIES)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new policy and its initial version 1 (OWNER or ADMIN only)."""
    return await policy_service.create_policy(
        db, project_id, policy_in, creator=str(current_user.id)
    )


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get policy details by ID (scoped by project membership)."""
    return await get_authorized_resource(
        db, SecurityPolicy, policy_id, "SecurityPolicy", current_user, Permission.VIEW_DASHBOARD
    )


@router.post("/policies/{policy_id}/versions", response_model=PolicyVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    policy_id: uuid.UUID,
    version_in: PolicyVersionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new immutable policy version (OWNER or ADMIN only).
    Never mutates existing version snapshots.
    """
    await get_authorized_resource(
        db, SecurityPolicy, policy_id, "SecurityPolicy", current_user, Permission.MANAGE_POLICIES
    )
    return await policy_service.create_policy_version(
        db, policy_id, version_in, creator=str(current_user.id)
    )


@router.get("/policies/{policy_id}/versions", response_model=List[PolicyVersionResponse])
async def list_versions(
    policy_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all version snapshots of a policy in descending order."""
    await get_authorized_resource(
        db, SecurityPolicy, policy_id, "SecurityPolicy", current_user, Permission.VIEW_DASHBOARD
    )
    return await policy_service.list_policy_versions(db, policy_id)


@router.post("/policies/{policy_id}/activate", response_model=PolicyVersionResponse)
async def activate_version(
    policy_id: uuid.UUID,
    activate_in: PolicyActivateVersion,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Activate a specific policy version snapshot (OWNER or ADMIN only)."""
    await get_authorized_resource(
        db, SecurityPolicy, policy_id, "SecurityPolicy", current_user, Permission.MANAGE_POLICIES
    )
    return await policy_service.activate_policy_version(db, policy_id, activate_in.version_id)
