# =============================================================================
# AgentGuard — Audit Logs Endpoints
# =============================================================================

import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.audit.schemas import AuditEventResponse
from app.auth.rbac import Permission, require_project_permission
from app.core.database import get_db
from app.persistence.models import AuditSeverity, User
from app.schemas.common import PaginatedResponse

router = APIRouter(tags=["Audit Logs"])


@router.get("/projects/{project_id}/audit-logs", response_model=PaginatedResponse[AuditEventResponse])
async def list_audit_logs(
    project_id: uuid.UUID,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[AuditSeverity] = Query(None, description="Filter by severity"),
    actor_id: Optional[uuid.UUID] = Query(None, description="Filter by actor ID"),
    execution_id: Optional[uuid.UUID] = Query(None, description="Filter by execution ID"),
    start_date: Optional[datetime] = Query(None, description="Filter from timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter until timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    _: User = Depends(require_project_permission(Permission.VIEW_AUDIT_LOGS)),
    db: AsyncSession = Depends(get_db),
):
    """Query append-only security audit events for a project."""
    items, total = await audit_service.list_audit_events(
        db=db,
        project_id=project_id,
        event_type=event_type,
        severity=severity,
        actor_id=actor_id,
        execution_id=execution_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[AuditEventResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
