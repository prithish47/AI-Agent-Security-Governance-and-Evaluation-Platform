# =============================================================================
# AgentGuard — Audit Service (Append-Only)
# =============================================================================

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import AuditEvent, AuditSeverity
from app.audit.schemas import AuditEventCreate


async def record_audit_event(
    db: AsyncSession, event_in: AuditEventCreate
) -> AuditEvent:
    """
    Append an immutable security event to the audit log.
    Never updates or deletes existing audit events.
    """
    event = AuditEvent(
        project_id=event_in.project_id,
        actor_id=event_in.actor_id,
        execution_id=event_in.execution_id,
        event_type=event_in.event_type,
        severity=event_in.severity,
        event_metadata=event_in.event_metadata,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_audit_events(
    db: AsyncSession,
    project_id: uuid.UUID,
    event_type: Optional[str] = None,
    severity: Optional[AuditSeverity] = None,
    actor_id: Optional[uuid.UUID] = None,
    execution_id: Optional[uuid.UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[List[AuditEvent], int]:
    stmt = select(AuditEvent).where(AuditEvent.project_id == project_id)

    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if severity:
        stmt = stmt.where(AuditEvent.severity == severity)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if execution_id:
        stmt = stmt.where(AuditEvent.execution_id == execution_id)
    if start_date:
        stmt = stmt.where(AuditEvent.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditEvent.created_at <= end_date)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total
