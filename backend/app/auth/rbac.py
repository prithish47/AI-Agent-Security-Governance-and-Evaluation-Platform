# =============================================================================
# AgentGuard — Centralized RBAC Permission System
# =============================================================================
# Implements the 5 project roles and strict separation of duties:
#
# OWNER:      Full control, delete project, manage membership
# ADMIN:      Manage members, policies, agents, tools, and configurations
# DEVELOPER:  Configure agents and tools, run executions and evaluations
# APPROVER:   Review and approve high-risk actions
# VIEWER:     Read-only dashboard access and audit inspection
#
# SEPARATION OF DUTIES:
# - Developers cannot approve high-risk operations.
# - Approvers cannot modify security policies or execute actions.
# - Viewers cannot modify or execute anything.
# =============================================================================

import enum
import uuid
from typing import Optional, Set
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.persistence.models import ProjectMember, ProjectRole, User


class Permission(str, enum.Enum):
    """Fine-grained application capabilities."""
    DELETE_PROJECT = "delete_project"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_POLICIES = "manage_policies"
    MANAGE_AGENTS = "manage_agents"
    MANAGE_TOOLS = "manage_tools"
    RUN_EXECUTIONS = "run_executions"
    RUN_EVALUATIONS = "run_evaluations"
    APPROVE_ACTIONS = "approve_actions"
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_AUDIT_LOGS = "view_audit_logs"


# Centralized capability matrix mapping roles to authorized permissions
ROLE_PERMISSIONS: dict[ProjectRole, Set[Permission]] = {
    ProjectRole.OWNER: {
        Permission.DELETE_PROJECT,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_POLICIES,
        Permission.MANAGE_AGENTS,
        Permission.MANAGE_TOOLS,
        Permission.RUN_EXECUTIONS,
        Permission.RUN_EVALUATIONS,
        Permission.APPROVE_ACTIONS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOGS,
    },
    ProjectRole.ADMIN: {
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_POLICIES,
        Permission.MANAGE_AGENTS,
        Permission.MANAGE_TOOLS,
        Permission.RUN_EXECUTIONS,
        Permission.RUN_EVALUATIONS,
        Permission.APPROVE_ACTIONS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOGS,
    },
    ProjectRole.DEVELOPER: {
        Permission.MANAGE_AGENTS,
        Permission.MANAGE_TOOLS,
        Permission.RUN_EXECUTIONS,
        Permission.RUN_EVALUATIONS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOGS,
    },
    ProjectRole.APPROVER: {
        Permission.APPROVE_ACTIONS,
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOGS,
    },
    ProjectRole.VIEWER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_AUDIT_LOGS,
    },
}


def has_permission(role: ProjectRole, permission: Permission) -> bool:
    """Check if a project role possesses a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency to extract and verify authenticated user from Authorization header.
    Format: Authorization: Bearer <token>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    user_id = uuid.UUID(payload["sub"])

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User does not exist or is inactive")
    return user


async def require_project_membership(
    project_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> ProjectMember:
    """Verify that user belongs to project and return their membership record."""
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id,
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if not member:
        raise ForbiddenError(f"User is not a member of project '{project_id}'")
    return member


async def verify_project_permission(
    project_id: uuid.UUID,
    user: User,
    permission: Permission,
    db: AsyncSession,
) -> ProjectMember:
    """
    Centralized authorization check.
    Enforces tenant isolation and role permissions.
    """
    member = await require_project_membership(project_id, user, db)
    if not has_permission(member.role, permission):
        raise ForbiddenError(
            f"Role '{member.role.value}' does not have permission '{permission.value}' in project '{project_id}'"
        )
    return member
