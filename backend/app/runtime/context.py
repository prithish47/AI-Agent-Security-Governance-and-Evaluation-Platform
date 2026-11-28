# =============================================================================
# AgentGuard — Pinned Execution Context Snapshot
# =============================================================================
# Context Pinning Guarantee:
# At execution start, snapshot the agent config, active policy version,
# assigned tools, risk ceiling, and policy rules.
# Mid-execution changes to database configuration NEVER affect an active execution.
# =============================================================================

import uuid
from typing import Any, Dict, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.persistence.models import (
    Agent,
    AgentToolAssignment,
    PolicyVersion,
    SecurityPolicy,
    ToolDefinition,
)
from app.policies.domain import RiskLevel, SecurityContext


async def create_pinned_context(
    db: AsyncSession, agent_id: uuid.UUID
) -> tuple[SecurityContext, Agent]:
    """
    Construct an immutable SecurityContext snapshot for an execution session.
    """
    # Fetch agent
    stmt = select(Agent).where(Agent.id == agent_id)
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent", str(agent_id))

    # Fetch assigned tools
    stmt = (
        select(ToolDefinition)
        .join(AgentToolAssignment, ToolDefinition.id == AgentToolAssignment.tool_id)
        .where(
            AgentToolAssignment.agent_id == agent_id,
            ToolDefinition.is_enabled == True,
        )
    )
    tools = list((await db.execute(stmt)).scalars().all())

    assigned_tool_names: Set[str] = {t.name for t in tools}
    tool_risk_levels: Dict[str, RiskLevel] = {
        t.name: RiskLevel(t.risk_level.value if hasattr(t.risk_level, "value") else str(t.risk_level))
        for t in tools
    }
    tool_schemas: Dict[str, Dict[str, Any]] = {t.name: t.input_schema for t in tools}

    # Fetch active policy snapshot
    policy_rules: Dict[str, Any] = {}
    policy_version_number = 1

    if agent.policy_id:
        policy = (
            await db.execute(
                select(SecurityPolicy).where(
                    SecurityPolicy.id == agent.policy_id,
                    SecurityPolicy.project_id == agent.project_id,
                )
            )
        ).scalar_one_or_none()

        if policy and policy.active_version_id:
            ver = (
                await db.execute(
                    select(PolicyVersion).where(PolicyVersion.id == policy.active_version_id)
                )
            ).scalar_one_or_none()
            if ver:
                policy_rules = ver.rules or {}
                policy_version_number = ver.version_number

    agent_risk = RiskLevel(agent.max_risk_level.value if hasattr(agent.max_risk_level, "value") else str(agent.max_risk_level))

    context = SecurityContext(
        agent_id=str(agent.id),
        project_id=str(agent.project_id),
        assigned_tools=assigned_tool_names,
        agent_risk_ceiling=agent_risk,
        tool_risk_levels=tool_risk_levels,
        tool_schemas=tool_schemas,
        policy_rules=policy_rules,
        policy_version_number=policy_version_number,
        policy_id=str(agent.policy_id) if agent.policy_id else None,
        authorized_resource_scopes={str(agent.project_id)},
    )

    return context, agent


async def reconstruct_or_load_pinned_context(
    db: AsyncSession,
    context_snapshot: Dict[str, Any],
    agent_id: uuid.UUID,
    project_id: uuid.UUID,
) -> SecurityContext:
    """
    Reconstruct the immutable SecurityContext from an execution's context_snapshot.
    If the snapshot contains all frozen tool schemas and rules, it is reconstructed
    in-memory with ZERO database queries. If older snapshot data lacks tool_schemas,
    it falls back to loading via create_pinned_context.
    """
    snap_tools = context_snapshot.get("assigned_tools")
    snap_schemas = context_snapshot.get("tool_schemas")

    if snap_tools is not None and snap_schemas is not None:
        agent_risk_raw = context_snapshot.get("agent_risk_ceiling", "MEDIUM")
        agent_risk = RiskLevel(agent_risk_raw)
        tool_risk_levels = {
            k: RiskLevel(v) for k, v in context_snapshot.get("tool_risk_levels", {}).items()
        }
        return SecurityContext(
            agent_id=str(agent_id),
            project_id=str(project_id),
            assigned_tools=set(snap_tools),
            agent_risk_ceiling=agent_risk,
            tool_risk_levels=tool_risk_levels,
            tool_schemas=snap_schemas,
            policy_rules=context_snapshot.get("policy_rules", {}),
            policy_version_number=context_snapshot.get("policy_version", 1),
            policy_id=context_snapshot.get("policy_id"),
            authorized_resource_scopes={str(project_id)},
        )

    # Fallback for legacy snapshots
    context, _ = await create_pinned_context(db, agent_id)
    return context
