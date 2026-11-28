# =============================================================================
# AgentGuard — Evaluation Schemas & Endpoints
# =============================================================================

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import (
    Permission,
    get_authorized_resource,
    get_current_user,
    require_project_permission,
)
from app.core.database import get_db
from app.evaluation.runner import EvaluationRunner
from app.persistence.models import EvaluationMode, EvaluationResult, EvaluationRun, User

router = APIRouter(tags=["Evaluations & Security Benchmarks"])


class EvaluationRunRequest(BaseModel):
    agent_id: UUID
    mode: EvaluationMode = EvaluationMode.BOTH


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    suite_id: UUID
    project_id: UUID
    agent_id: UUID
    mode: EvaluationMode
    status: str
    metrics: Dict[str, Any]
    started_at: datetime
    completed_at: Optional[datetime]


class EvaluationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    case_id: UUID
    actual_result: str
    attack_succeeded: bool
    tool_executed: bool
    legitimate_succeeded: bool
    false_blocked: bool
    execution_latency_ms: float
    policy_eval_latency_ms: Optional[float]
    failure_reason: Optional[str]
    created_at: datetime


@router.get("/projects/{project_id}/evaluations", response_model=List[EvaluationRunResponse])
async def list_project_evaluations(
    project_id: UUID,
    _: User = Depends(require_project_permission(Permission.VIEW_DASHBOARD)),
    db: AsyncSession = Depends(get_db),
):
    """List all benchmark evaluation runs for a project."""
    stmt = select(EvaluationRun).where(EvaluationRun.project_id == project_id).order_by(EvaluationRun.started_at.desc())
    runs = list((await db.execute(stmt)).scalars().all())
    return runs


@router.post("/projects/{project_id}/evaluations/run", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
async def run_evaluation_benchmark(
    project_id: UUID,
    run_in: EvaluationRunRequest,
    current_user: User = Depends(require_project_permission(Permission.RUN_EVALUATIONS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute the 21-case adversarial and reliability security benchmark.
    Calculates ASR, UTER, LTSR, FBR, and interception latencies from real results.
    """
    return await EvaluationRunner.run_suite(
        db=db,
        project_id=project_id,
        agent_id=run_in.agent_id,
        mode=run_in.mode,
        actor_id=current_user.id,
    )


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(
    evaluation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation run status and comparison metrics."""
    return await get_authorized_resource(
        db, EvaluationRun, evaluation_id, "EvaluationRun", current_user, Permission.VIEW_DASHBOARD
    )


@router.get("/evaluations/{evaluation_id}/results", response_model=List[EvaluationResultResponse])
async def get_evaluation_results(
    evaluation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed case-by-case benchmark results for a run (scoped by project membership)."""
    await get_authorized_resource(
        db, EvaluationRun, evaluation_id, "EvaluationRun", current_user, Permission.VIEW_DASHBOARD
    )
    stmt = select(EvaluationResult).where(EvaluationResult.run_id == evaluation_id).order_by(EvaluationResult.created_at.asc())
    results = list((await db.execute(stmt)).scalars().all())
    return results
