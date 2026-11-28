# =============================================================================
# AgentGuard — Tools Endpoints
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
from app.persistence.models import ToolDefinition, User
from app.tools import service as tool_service
from app.tools.schemas import ToolCreate, ToolUpdate, ToolResponse

router = APIRouter(tags=["Tools"])


def _to_tool_response(t: ToolDefinition) -> ToolResponse:
    return ToolResponse(
        id=t.id,
        project_id=t.project_id,
        name=t.name,
        description=t.description,
        input_schema=t.input_schema,
        risk_level=t.risk_level,
        is_enabled=t.is_enabled,
        is_executable=tool_service.check_is_executable(t.name),
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/projects/{project_id}/tools", response_model=List[ToolResponse])
async def list_project_tools(
    project_id: uuid.UUID,
    _: User = Depends(require_project_permission(Permission.VIEW_DASHBOARD)),
    db: AsyncSession = Depends(get_db),
):
    """List all registered tools in a project."""
    tools = await tool_service.list_project_tools(db, project_id)
    return [_to_tool_response(t) for t in tools]


@router.post("/projects/{project_id}/tools", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    project_id: uuid.UUID,
    tool_in: ToolCreate,
    _: User = Depends(require_project_permission(Permission.MANAGE_TOOLS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Register tool metadata in a project.

    CRITICAL: This stores metadata only, never executable code.
    """
    t = await tool_service.create_tool(db, project_id, tool_in)
    return _to_tool_response(t)


@router.get("/tools/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get tool metadata by ID (scoped by project membership)."""
    t = await get_authorized_resource(
        db, ToolDefinition, tool_id, "ToolDefinition", current_user, Permission.VIEW_DASHBOARD
    )
    return _to_tool_response(t)


@router.patch("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: uuid.UUID,
    tool_in: ToolUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update tool metadata (requires MANAGE_TOOLS in tool's project)."""
    await get_authorized_resource(
        db, ToolDefinition, tool_id, "ToolDefinition", current_user, Permission.MANAGE_TOOLS
    )
    t = await tool_service.update_tool(db, tool_id, tool_in)
    return _to_tool_response(t)


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a tool definition (requires MANAGE_TOOLS in tool's project)."""
    await get_authorized_resource(
        db, ToolDefinition, tool_id, "ToolDefinition", current_user, Permission.MANAGE_TOOLS
    )
    await tool_service.delete_tool(db, tool_id)
