# =============================================================================
# AgentGuard — Tool Service
# =============================================================================

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.persistence.models import ToolDefinition
from app.tools.schemas import ToolCreate, ToolUpdate

# Catalog whitelist of precompiled executable tools in Python
EXECUTABLE_TOOLS_WHITELIST = {
    "search_customer",
    "get_customer_details",
    "get_support_ticket",
    "update_ticket_status",
    "get_order_status",
    "calculate_refund",
    "issue_refund",
    "search_knowledge_base",
}


async def create_tool(
    db: AsyncSession, project_id: uuid.UUID, tool_in: ToolCreate
) -> ToolDefinition:
    stmt = select(ToolDefinition).where(
        ToolDefinition.project_id == project_id,
        ToolDefinition.name == tool_in.name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Tool with name '{tool_in.name}' already exists in this project")

    tool = ToolDefinition(
        project_id=project_id,
        name=tool_in.name,
        description=tool_in.description,
        input_schema=tool_in.input_schema,
        risk_level=tool_in.risk_level,
        is_enabled=tool_in.is_enabled,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


async def get_tool(db: AsyncSession, tool_id: uuid.UUID) -> ToolDefinition:
    stmt = select(ToolDefinition).where(ToolDefinition.id == tool_id)
    tool = (await db.execute(stmt)).scalar_one_or_none()
    if not tool:
        raise NotFoundError("ToolDefinition", str(tool_id))
    return tool


async def list_project_tools(
    db: AsyncSession, project_id: uuid.UUID
) -> List[ToolDefinition]:
    stmt = select(ToolDefinition).where(ToolDefinition.project_id == project_id).order_by(ToolDefinition.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_tool(
    db: AsyncSession, tool_id: uuid.UUID, tool_in: ToolUpdate
) -> ToolDefinition:
    tool = await get_tool(db, tool_id)
    if tool_in.description is not None:
        tool.description = tool_in.description
    if tool_in.input_schema is not None:
        tool.input_schema = tool_in.input_schema
    if tool_in.risk_level is not None:
        tool.risk_level = tool_in.risk_level
    if tool_in.is_enabled is not None:
        tool.is_enabled = tool_in.is_enabled

    await db.commit()
    await db.refresh(tool)
    return tool


async def delete_tool(db: AsyncSession, tool_id: uuid.UUID) -> None:
    tool = await get_tool(db, tool_id)
    await db.delete(tool)
    await db.commit()


def check_is_executable(tool_name: str) -> bool:
    """Check if tool has an implementation in the precompiled catalog."""
    return tool_name in EXECUTABLE_TOOLS_WHITELIST
