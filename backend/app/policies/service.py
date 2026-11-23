# =============================================================================
# AgentGuard — Security Policy Service
# =============================================================================

import uuid
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.persistence.models import SecurityPolicy, PolicyVersion
from app.policies.schemas import PolicyCreate, PolicyVersionCreate


async def create_policy(
    db: AsyncSession, project_id: uuid.UUID, policy_in: PolicyCreate, creator: Optional[str] = None
) -> SecurityPolicy:
    policy = SecurityPolicy(
        project_id=project_id,
        name=policy_in.name,
        description=policy_in.description,
    )
    db.add(policy)
    await db.flush()

    # Create immutable initial version 1 and mark active
    v1 = PolicyVersion(
        policy_id=policy.id,
        version_number=1,
        rules=policy_in.rules,
        is_active=True,
        created_by=creator,
    )
    db.add(v1)
    await db.flush()

    policy.active_version_id = v1.id
    await db.commit()
    await db.refresh(policy)
    return policy


async def get_policy(db: AsyncSession, policy_id: uuid.UUID) -> SecurityPolicy:
    stmt = select(SecurityPolicy).where(SecurityPolicy.id == policy_id)
    policy = (await db.execute(stmt)).scalar_one_or_none()
    if not policy:
        raise NotFoundError("SecurityPolicy", str(policy_id))
    return policy


async def list_project_policies(
    db: AsyncSession, project_id: uuid.UUID
) -> List[SecurityPolicy]:
    stmt = select(SecurityPolicy).where(SecurityPolicy.project_id == project_id).order_by(SecurityPolicy.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_policy_version(
    db: AsyncSession, policy_id: uuid.UUID, version_in: PolicyVersionCreate, creator: Optional[str] = None
) -> PolicyVersion:
    policy = await get_policy(db, policy_id)

    # Determine next version number
    stmt = select(PolicyVersion.version_number).where(
        PolicyVersion.policy_id == policy_id
    ).order_by(PolicyVersion.version_number.desc()).limit(1)
    max_ver = (await db.execute(stmt)).scalar_one_or_none() or 0
    next_ver = max_ver + 1

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=next_ver,
        rules=version_in.rules,
        is_active=False,
        created_by=creator,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def list_policy_versions(
    db: AsyncSession, policy_id: uuid.UUID
) -> List[PolicyVersion]:
    await get_policy(db, policy_id)
    stmt = select(PolicyVersion).where(
        PolicyVersion.policy_id == policy_id
    ).order_by(PolicyVersion.version_number.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def activate_policy_version(
    db: AsyncSession, policy_id: uuid.UUID, version_id: uuid.UUID
) -> PolicyVersion:
    policy = await get_policy(db, policy_id)

    stmt = select(PolicyVersion).where(
        PolicyVersion.id == version_id,
        PolicyVersion.policy_id == policy_id,
    )
    target_version = (await db.execute(stmt)).scalar_one_or_none()
    if not target_version:
        raise NotFoundError("PolicyVersion", str(version_id))

    # Deactivate all versions for this policy
    await db.execute(
        update(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .values(is_active=False)
    )

    # Activate selected version
    target_version.is_active = True
    policy.active_version_id = target_version.id

    await db.commit()
    await db.refresh(target_version)
    return target_version
