# =============================================================================
# AgentGuard — Project Schemas
# =============================================================================

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import ProjectRole


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Workspace name")
    description: Optional[str] = Field(None, max_length=2000, description="Workspace description")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)


class ProjectMemberCreate(BaseModel):
    user_id: UUID
    role: ProjectRole = Field(default=ProjectRole.DEVELOPER)


class ProjectMemberUpdate(BaseModel):
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    role: ProjectRole
    created_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
