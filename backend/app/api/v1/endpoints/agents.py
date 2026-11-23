# =============================================================================
# AgentGuard — Agents Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.agents import service as agent_service
from app.agents.schemas import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentToolAssignmentCreate,
    AgentToolAssignmentResponse,
)

router = APIRouter(tags=["Agents"])


@router.get("/projects/{project_id}/agents", response_model=List[AgentResponse])
async def list_project_agents(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all agents in a project."""
    return await agent_service.list_project_agents(db, project_id)


@router.post("/projects/{project_id}/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    project_id: uuid.UUID, agent_in: AgentCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new AI agent configuration in a project."""
    return await agent_service.create_agent(db, project_id, agent_in)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get an agent by ID."""
    return await agent_service.get_agent(db, agent_id)


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID, agent_in: AgentUpdate, db: AsyncSession = Depends(get_db)
):
    """Update agent configuration."""
    return await agent_service.update_agent(db, agent_id, agent_in)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete an agent."""
    await agent_service.delete_agent(db, agent_id)


@router.post("/agents/{agent_id}/tools", response_model=AgentToolAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_tool(
    agent_id: uuid.UUID, assignment_in: AgentToolAssignmentCreate, db: AsyncSession = Depends(get_db)
):
    """Assign a tool to an agent."""
    return await agent_service.assign_tool_to_agent(db, agent_id, assignment_in.tool_id)


@router.delete("/agents/{agent_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_tool(
    agent_id: uuid.UUID, tool_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Unassign a tool from an agent."""
    await agent_service.unassign_tool_from_agent(db, agent_id, tool_id)
