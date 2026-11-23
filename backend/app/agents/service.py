# =============================================================================
# AgentGuard — Agent Service
# =============================================================================

import uuid
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.persistence.models import Agent, AgentToolAssignment, ToolDefinition
from app.agents.schemas import AgentCreate, AgentUpdate


async def create_agent(
    db: AsyncSession, project_id: uuid.UUID, agent_in: AgentCreate
) -> Agent:
    # Check for duplicate agent name within project
    stmt = select(Agent).where(Agent.project_id == project_id, Agent.name == agent_in.name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Agent with name '{agent_in.name}' already exists in this project")

    agent = Agent(
        project_id=project_id,
        name=agent_in.name,
        description=agent_in.description,
        system_prompt=agent_in.system_prompt,
        model_provider=agent_in.model_provider,
        model_name=agent_in.model_name,
        max_iterations=agent_in.max_iterations,
        max_risk_level=agent_in.max_risk_level,
        policy_id=agent_in.policy_id,
        is_enabled=agent_in.is_enabled,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> Agent:
    stmt = select(Agent).where(Agent.id == agent_id)
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent", str(agent_id))
    return agent


async def list_project_agents(
    db: AsyncSession, project_id: uuid.UUID
) -> List[Agent]:
    stmt = select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_agent(
    db: AsyncSession, agent_id: uuid.UUID, agent_in: AgentUpdate
) -> Agent:
    agent = await get_agent(db, agent_id)

    if agent_in.name is not None and agent_in.name != agent.name:
        # Check uniqueness
        stmt = select(Agent).where(
            Agent.project_id == agent.project_id,
            Agent.name == agent_in.name,
            Agent.id != agent_id,
        )
        if (await db.execute(stmt)).scalar_one_or_none():
            raise ConflictError(f"Agent name '{agent_in.name}' already exists in project")
        agent.name = agent_in.name

    if agent_in.description is not None:
        agent.description = agent_in.description
    if agent_in.system_prompt is not None:
        agent.system_prompt = agent_in.system_prompt
    if agent_in.model_provider is not None:
        agent.model_provider = agent_in.model_provider
    if agent_in.model_name is not None:
        agent.model_name = agent_in.model_name
    if agent_in.max_iterations is not None:
        agent.max_iterations = agent_in.max_iterations
    if agent_in.max_risk_level is not None:
        agent.max_risk_level = agent_in.max_risk_level
    if agent_in.policy_id is not None:
        agent.policy_id = agent_in.policy_id
    if agent_in.is_enabled is not None:
        agent.is_enabled = agent_in.is_enabled

    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, agent_id: uuid.UUID) -> None:
    agent = await get_agent(db, agent_id)
    await db.delete(agent)
    await db.commit()


async def assign_tool_to_agent(
    db: AsyncSession, agent_id: uuid.UUID, tool_id: uuid.UUID
) -> AgentToolAssignment:
    agent = await get_agent(db, agent_id)

    # Verify tool exists and belongs to the same project
    stmt = select(ToolDefinition).where(
        ToolDefinition.id == tool_id,
        ToolDefinition.project_id == agent.project_id,
    )
    tool = (await db.execute(stmt)).scalar_one_or_none()
    if not tool:
        raise NotFoundError("ToolDefinition", str(tool_id))

    # Check if already assigned
    stmt = select(AgentToolAssignment).where(
        AgentToolAssignment.agent_id == agent_id,
        AgentToolAssignment.tool_id == tool_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictError("Tool is already assigned to this agent")

    assignment = AgentToolAssignment(
        agent_id=agent_id,
        tool_id=tool_id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def unassign_tool_from_agent(
    db: AsyncSession, agent_id: uuid.UUID, tool_id: uuid.UUID
) -> None:
    stmt = select(AgentToolAssignment).where(
        AgentToolAssignment.agent_id == agent_id,
        AgentToolAssignment.tool_id == tool_id,
    )
    assignment = (await db.execute(stmt)).scalar_one_or_none()
    if not assignment:
        raise NotFoundError("AgentToolAssignment", f"{agent_id}:{tool_id}")
    await db.delete(assignment)
    await db.commit()
