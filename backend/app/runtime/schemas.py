# =============================================================================
# AgentGuard — Runtime & Execution Schemas
# =============================================================================

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import ExecutionStatus


class ExecutionTaskRequest(BaseModel):
    task: str = Field(..., min_length=2, max_length=5000, description="Task prompt for the AI agent")


class ExecutionStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_number: int
    step_type: str
    tool_name: Optional[str]
    tool_arguments: Optional[Dict[str, Any]]
    policy_decision: Optional[str]
    policy_rule: Optional[str]
    policy_reason: Optional[str]
    tool_result: Optional[Dict[str, Any]]
    model_response: Optional[str]
    policy_eval_ms: Optional[float]
    created_at: datetime


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    agent_id: UUID
    task_prompt: str
    status: ExecutionStatus
    termination_reason: Optional[str]
    final_response: Optional[str]
    iteration_count: int
    started_at: datetime
    completed_at: Optional[datetime]


class ExecutionTraceResponse(BaseModel):
    execution: ExecutionResponse
    steps: List[ExecutionStepResponse]
