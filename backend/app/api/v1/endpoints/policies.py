# =============================================================================
# AgentGuard — Security Policies Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
async def list_project_policies(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all policies in a project."""
    return await policy_service.list_project_policies(db, project_id)


@router.post("/projects/{project_id}/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    project_id: uuid.UUID, policy_in: PolicyCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new policy and its initial version 1."""
    return await policy_service.create_policy(db, project_id, policy_in)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get policy details by ID."""
    return await policy_service.get_policy(db, policy_id)


@router.post("/policies/{policy_id}/versions", response_model=PolicyVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    policy_id: uuid.UUID, version_in: PolicyVersionCreate, db: AsyncSession = Depends(get_db)
):
    """
    Create a new immutable policy version.
    Never mutates existing version snapshots.
    """
    return await policy_service.create_policy_version(db, policy_id, version_in)


@router.get("/policies/{policy_id}/versions", response_model=List[PolicyVersionResponse])
async def list_versions(policy_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all version snapshots of a policy in descending order."""
    return await policy_service.list_policy_versions(db, policy_id)


@router.post("/policies/{policy_id}/activate", response_model=PolicyVersionResponse)
async def activate_version(
    policy_id: uuid.UUID, activate_in: PolicyActivateVersion, db: AsyncSession = Depends(get_db)
):
    """Activate a specific policy version snapshot."""
    return await policy_service.activate_policy_version(db, policy_id, activate_in.version_id)
