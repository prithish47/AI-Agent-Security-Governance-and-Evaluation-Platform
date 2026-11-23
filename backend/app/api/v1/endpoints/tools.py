# =============================================================================
# AgentGuard — Tools Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.tools import service as tool_service
from app.tools.schemas import ToolCreate, ToolUpdate, ToolResponse

router = APIRouter(tags=["Tools"])


@router.get("/projects/{project_id}/tools", response_model=List[ToolResponse])
async def list_project_tools(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all registered tools in a project."""
    tools = await tool_service.list_project_tools(db, project_id)
    return [
        ToolResponse(
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
        for t in tools
    ]


@router.post("/projects/{project_id}/tools", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    project_id: uuid.UUID, tool_in: ToolCreate, db: AsyncSession = Depends(get_db)
):
    """
    Register tool metadata in a project.
    
    CRITICAL: This stores metadata only, never executable code.
    """
    t = await tool_service.create_tool(db, project_id, tool_in)
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


@router.get("/tools/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get tool metadata by ID."""
    t = await tool_service.get_tool(db, tool_id)
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


@router.patch("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: uuid.UUID, tool_in: ToolUpdate, db: AsyncSession = Depends(get_db)
):
    """Update tool metadata."""
    t = await tool_service.update_tool(db, tool_id, tool_in)
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


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete a tool definition."""
    await tool_service.delete_tool(db, tool_id)
