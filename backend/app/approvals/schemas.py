# =============================================================================
# AgentGuard — Human Approval Schemas
# =============================================================================

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import ApprovalStatus


class ApprovalReviewRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=1000, description="Approver review comment or reason")


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    execution_id: UUID
    agent_id: UUID
    tool_name: str
    tool_arguments: Dict[str, Any]
    policy_version: int
    agent_risk_ceiling: str
    action_hash: str
    status: ApprovalStatus
    reviewed_by: Optional[UUID]
    review_note: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]
    expires_at: Optional[datetime]
