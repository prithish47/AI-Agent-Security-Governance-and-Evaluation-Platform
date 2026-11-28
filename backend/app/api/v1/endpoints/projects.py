# =============================================================================
# AgentGuard — Projects Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import (
    Permission,
    get_current_user,
    require_project_permission,
    verify_project_permission,
)
from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.persistence.models import ProjectRole, User
from app.projects import service as project_service
from app.projects.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects the authenticated user is a member of."""
    return await project_service.list_projects(db, user_id=current_user.id)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project workspace with the authenticated user as OWNER."""
    return await project_service.create_project(db, project_in, creator_id=current_user.id)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    _: User = Depends(require_project_permission(Permission.VIEW_DASHBOARD)),
    db: AsyncSession = Depends(get_db),
):
    """Get project details by ID (requires project membership)."""
    return await project_service.get_project(db, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    _: User = Depends(require_project_permission(Permission.MANAGE_PROJECT)),
    db: AsyncSession = Depends(get_db),
):
    """Update project details (OWNER or ADMIN only)."""
    return await project_service.update_project(db, project_id, project_in)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    _: User = Depends(require_project_permission(Permission.DELETE_PROJECT)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project and all associated resources (OWNER only)."""
    await project_service.delete_project(db, project_id)


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
async def list_members(
    project_id: uuid.UUID,
    _: User = Depends(require_project_permission(Permission.VIEW_DASHBOARD)),
    db: AsyncSession = Depends(get_db),
):
    """List members of a project."""
    return await project_service.list_project_members(db, project_id)


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    member_in: ProjectMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a project with a specific role (OWNER or ADMIN only)."""
    acting_member = await verify_project_permission(
        project_id, current_user, Permission.MANAGE_MEMBERS, db
    )
    if member_in.role == ProjectRole.OWNER and acting_member.role != ProjectRole.OWNER:
        raise ForbiddenError("Only project owners can assign the OWNER role")
    return await project_service.add_project_member(db, project_id, member_in)
