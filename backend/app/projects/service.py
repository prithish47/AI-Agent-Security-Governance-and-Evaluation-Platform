# =============================================================================
# AgentGuard — Project Service
# =============================================================================

import uuid
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.persistence.models import Project, ProjectMember, ProjectRole, User
from app.projects.schemas import ProjectCreate, ProjectUpdate, ProjectMemberCreate


async def create_project(
    db: AsyncSession, project_in: ProjectCreate, creator_id: Optional[uuid.UUID] = None
) -> Project:
    project = Project(
        name=project_in.name,
        description=project_in.description,
    )
    db.add(project)
    await db.flush()

    if creator_id:
        member = ProjectMember(
            project_id=project.id,
            user_id=creator_id,
            role=ProjectRole.OWNER,
        )
        db.add(member)
        await db.flush()

    await db.commit()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project", str(project_id))
    return project


async def list_projects(
    db: AsyncSession, user_id: Optional[uuid.UUID] = None
) -> List[Project]:
    if user_id:
        stmt = (
            select(Project)
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .where(ProjectMember.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
    else:
        stmt = select(Project).order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_project(
    db: AsyncSession, project_id: uuid.UUID, project_in: ProjectUpdate
) -> Project:
    project = await get_project(db, project_id)
    if project_in.name is not None:
        project.name = project_in.name
    if project_in.description is not None:
        project.description = project_in.description
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    project = await get_project(db, project_id)
    await db.delete(project)
    await db.commit()


async def add_project_member(
    db: AsyncSession, project_id: uuid.UUID, member_in: ProjectMemberCreate
) -> ProjectMember:
    await get_project(db, project_id)

    # Verify target user exists
    user_stmt = select(User).where(User.id == member_in.user_id)
    target_user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not target_user:
        raise NotFoundError("User", str(member_in.user_id))

    # Check if already a member
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == member_in.user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"User {member_in.user_id} is already a member of project {project_id}")

    member = ProjectMember(
        project_id=project_id,
        user_id=member_in.user_id,
        role=member_in.role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def list_project_members(
    db: AsyncSession, project_id: uuid.UUID
) -> List[ProjectMember]:
    await get_project(db, project_id)
    stmt = select(ProjectMember).where(ProjectMember.project_id == project_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
