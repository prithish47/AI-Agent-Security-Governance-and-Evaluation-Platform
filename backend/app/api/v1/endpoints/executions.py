# =============================================================================
# AgentGuard — Execution & Trace Endpoints
# =============================================================================

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.persistence.models import Execution, ExecutionStep
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
    db: AsyncSession = Depends(get_db),
):
    """
    Run an agent through the guarded runtime pipeline with a task prompt.
    Interception is guaranteed.
    """
    return await AgentRuntimeOrchestrator.execute_task(
        db=db,
        agent_id=agent_id,
        task_prompt=task_in.task,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get execution status and details."""
    stmt = select(Execution).where(Execution.id == execution_id)
    execution = (await db.execute(stmt)).scalar_one_or_none()
    if not execution:
        raise NotFoundError("Execution", str(execution_id))
    return execution


@router.get("/executions/{execution_id}/trace", response_model=ExecutionTraceResponse)
async def get_execution_trace(execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get full step-by-step execution trace including tool proposals and policy decisions."""
    stmt = select(Execution).where(Execution.id == execution_id)
    execution = (await db.execute(stmt)).scalar_one_or_none()
    if not execution:
        raise NotFoundError("Execution", str(execution_id))

    stmt_steps = select(ExecutionStep).where(
        ExecutionStep.execution_id == execution_id
    ).order_by(ExecutionStep.step_number.asc())
    steps = list((await db.execute(stmt_steps)).scalars().all())

    return ExecutionTraceResponse(
        execution=ExecutionResponse.model_validate(execution),
        steps=[ExecutionStepResponse.model_validate(s) for s in steps],
    )
