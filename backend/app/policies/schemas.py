# =============================================================================
# AgentGuard — Security Policy Schemas
# =============================================================================

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PolicyRuleConfig(BaseModel):
    """Structured configuration for the 7 security policy rules."""
    denied_tools: List[str] = Field(default_factory=list, description="Explicitly blocked tool names")
    approval_required_tools: List[str] = Field(default_factory=list, description="Tools requiring human approval")
    max_argument_size_bytes: int = Field(default=10000, description="Max allowed argument payload size")
    max_array_size: int = Field(default=50, description="Max elements in an argument array")
    disallowed_patterns: List[str] = Field(default_factory=list, description="Regex patterns to flag suspicious content")
    allowed_resource_scopes: List[str] = Field(default_factory=list, description="Explicit allowed resource prefixes")


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    rules: Dict[str, Any] = Field(default_factory=dict, description="Initial rule set for version 1")


class PolicyVersionCreate(BaseModel):
    rules: Dict[str, Any] = Field(..., description="Complete snapshot of rules for the new immutable version")


class PolicyActivateVersion(BaseModel):
    version_id: UUID


class PolicyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_id: UUID
    version_number: int
    rules: Dict[str, Any]
    is_active: bool
    created_by: Optional[str]
    created_at: datetime


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    active_version_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
