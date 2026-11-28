# =============================================================================
# AgentGuard — Execution & Trace Endpoints
# =============================================================================

import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import Permission, get_authorized_resource, get_current_user
from app.core.database import get_db
from app.persistence.models import Agent, Execution, ExecutionStep, User
from app.runtime.orchestrator import AgentRuntimeOrchestrator
from app.runtime.schemas import (
    ExecutionResponse,
    ExecutionStepResponse,
    ExecutionTaskRequest,
    ExecutionTraceResponse,
)

router = APIRouter(tags=["Agent Execution & Playground"])


@router.post("/agents/{agent_id}/execute", response_model=ExecutionResponse, status_code=status.HTTP_200_OK)
async def execute_agent(
    agent_id: uuid.UUID,
    task_in: ExecutionTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run an agent through the guarded runtime pipeline with a task prompt.
    Interception is guaranteed. Requires RUN_EXECUTIONS permission in agent's project.
    """
    await get_authorized_resource(
        db, Agent, agent_id, "Agent", current_user, Permission.RUN_EXECUTIONS
    )
    return await AgentRuntimeOrchestrator.execute_task(
        db=db,
        agent_id=agent_id,
        task_prompt=task_in.task,
        user_id=current_user.id,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get execution status and details (scoped by project membership)."""
    return await get_authorized_resource(
        db, Execution, execution_id, "Execution", current_user, Permission.VIEW_DASHBOARD
    )


@router.get("/executions/{execution_id}/trace", response_model=ExecutionTraceResponse)
async def get_execution_trace(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full step-by-step execution trace including tool proposals and policy decisions."""
    execution = await get_authorized_resource(
        db, Execution, execution_id, "Execution", current_user, Permission.VIEW_DASHBOARD
    )

    stmt_steps = select(ExecutionStep).where(
        ExecutionStep.execution_id == execution_id
    ).order_by(ExecutionStep.step_number.asc())
    steps = list((await db.execute(stmt_steps)).scalars().all())

    return ExecutionTraceResponse(
        execution=ExecutionResponse.model_validate(execution),
        steps=[ExecutionStepResponse.model_validate(s) for s in steps],
    )
