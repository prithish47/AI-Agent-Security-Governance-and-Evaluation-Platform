# =============================================================================
# AgentGuard — Agent Schemas
# =============================================================================

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import RiskLevel


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    system_prompt: str = Field(default="You are a secure, helpful AI assistant.", max_length=10000)
    model_provider: str = Field(default="mock", max_length=50)
    model_name: str = Field(default="mock-model", max_length=100)
    max_iterations: int = Field(default=10, ge=1, le=20)
    max_risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)
    policy_id: Optional[UUID] = None
    is_enabled: bool = Field(default=True)


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    system_prompt: Optional[str] = Field(None, max_length=10000)
    model_provider: Optional[str] = Field(None, max_length=50)
    model_name: Optional[str] = Field(None, max_length=100)
    max_iterations: Optional[int] = Field(None, ge=1, le=20)
    max_risk_level: Optional[RiskLevel] = None
    policy_id: Optional[UUID] = None
    is_enabled: Optional[bool] = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    system_prompt: str
    model_provider: str
    model_name: str
    max_iterations: int
    max_risk_level: RiskLevel
    policy_id: Optional[UUID]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class AgentToolAssignmentCreate(BaseModel):
    tool_id: UUID


class AgentToolAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tool_id: UUID
    created_at: datetime
