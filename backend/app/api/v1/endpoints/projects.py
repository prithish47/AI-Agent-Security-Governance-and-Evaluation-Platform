# =============================================================================
# AgentGuard — Projects Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
async def list_projects(db: AsyncSession = Depends(get_db)):
    """List all projects."""
    return await project_service.list_projects(db)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project_in: ProjectCreate, db: AsyncSession = Depends(get_db)):
    """Create a new project workspace."""
    return await project_service.create_project(db, project_in)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get project details by ID."""
    return await project_service.get_project(db, project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, project_in: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    """Update project details."""
    return await project_service.update_project(db, project_id, project_in)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a project and all associated resources."""
    await project_service.delete_project(db, project_id)


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
async def list_members(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List members of a project."""
    return await project_service.list_project_members(db, project_id)


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID, member_in: ProjectMemberCreate, db: AsyncSession = Depends(get_db)
):
    """Add a member to a project with a specific role."""
    return await project_service.add_project_member(db, project_id, member_in)
