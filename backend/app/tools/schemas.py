# =============================================================================
# AgentGuard — Tool Schemas
# =============================================================================

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import RiskLevel


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=5, max_length=2000)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    is_enabled: bool = Field(default=True)


class ToolUpdate(BaseModel):
    description: Optional[str] = Field(None, min_length=5, max_length=2000)
    input_schema: Optional[Dict[str, Any]] = None
    risk_level: Optional[RiskLevel] = None
    is_enabled: Optional[bool] = None


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str
    input_schema: Dict[str, Any]
    risk_level: RiskLevel
    is_enabled: bool
    is_executable: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime
