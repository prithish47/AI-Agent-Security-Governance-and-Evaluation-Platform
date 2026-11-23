# =============================================================================
# AgentGuard — Audit Schemas
# =============================================================================

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.persistence.models import AuditSeverity


class AuditEventCreate(BaseModel):
    project_id: UUID
    actor_id: Optional[UUID] = None
    execution_id: Optional[UUID] = None
    event_type: str
    severity: AuditSeverity = AuditSeverity.INFO
    event_metadata: Dict[str, Any] = {}


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    actor_id: Optional[UUID]
    execution_id: Optional[UUID]
    event_type: str
    severity: AuditSeverity
    event_metadata: Dict[str, Any]
    created_at: datetime
