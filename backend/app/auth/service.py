# =============================================================================
# AgentGuard — Authentication Service
# =============================================================================

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError, NotFoundError
from app.core.security import (
    hash_password,
    verify_password,
    hash_token,
    create_access_token,
    create_refresh_token,
)
from app.persistence.models import User, RefreshToken
from app.auth.schemas import UserRegister, UserLogin, TokenResponse


async def register_user(db: AsyncSession, register_in: UserRegister) -> User:
    """Register a new user account with Argon2id password hashing."""
    # Check duplicate email
    stmt = select(User).where(User.email == register_in.email)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise ConflictError(f"Email '{register_in.email}' is already registered")

    # Check duplicate username
    stmt = select(User).where(User.username == register_in.username)
    if (await db.execute(stmt)).scalar_one_or_none():
        raise ConflictError(f"Username '{register_in.username}' is already taken")

    user = User(
        email=register_in.email,
        username=register_in.username,
        password_hash=hash_password(register_in.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, login_in: UserLogin) -> User:
    """Authenticate credentials against stored Argon2id password hash."""
    stmt = select(User).where(User.email == login_in.email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")
    return user


async def create_tokens_for_user(db: AsyncSession, user: User) -> TokenResponse:
    """Generate JWT access token and persist hashed refresh token with a new family_id."""
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
    )
    raw_refresh_token, expires_at = create_refresh_token(user_id=user.id)
    family_id = uuid.uuid4()

    # Store hashed refresh token in DB
    token_record = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_token(raw_refresh_token),
        is_revoked=False,
        expires_at=expires_at,
    )
    db.add(token_record)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def _revoke_token_family(
    db: AsyncSession, family_id: uuid.UUID, revoked_at: datetime
) -> None:
    """Revoke every active refresh token belonging to a session family."""
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.family_id == family_id,
            RefreshToken.is_revoked == False,
        )
        .values(is_revoked=True, revoked_at=revoked_at)
    )


async def refresh_access_token(db: AsyncSession, raw_refresh_token: str) -> TokenResponse:
    """
    Validate refresh token and atomically rotate to a new refresh token:
    - Detects reuse of an already-rotated token and revokes the entire token family.
    - Uses an atomic conditional UPDATE (is_revoked == False) to prevent concurrent reuse.
    - Rejects expired and revoked tokens.
    """
    token_hashed = hash_token(raw_refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hashed)
    record = (await db.execute(stmt)).scalar_one_or_none()

    if not record:
        raise UnauthorizedError("Invalid or revoked refresh token")

    now = datetime.now(timezone.utc)
    record_exp = (
        record.expires_at.replace(tzinfo=timezone.utc)
        if record.expires_at.tzinfo is None
        else record.expires_at
    )

    # Reuse / revocation check
    if record.is_revoked:
        if record.replaced_by_token_id is not None:
            # Previously rotated token was replayed -> compromise/reuse detected; revoke family
            await _revoke_token_family(db, record.family_id, now)
            await db.commit()
            raise UnauthorizedError("Refresh token reuse detected; session revoked")
        raise UnauthorizedError("Invalid or revoked refresh token")

    if record_exp < now:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == record.id, RefreshToken.is_revoked == False)
            .values(is_revoked=True, revoked_at=now)
        )
        await db.commit()
        raise UnauthorizedError("Refresh token has expired")

    # Verify user is active
    user = (await db.execute(select(User).where(User.id == record.user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        await _revoke_token_family(db, record.family_id, now)
        await db.commit()
        raise UnauthorizedError("User account is not active")

    # Generate replacement refresh token
    new_token_id = uuid.uuid4()
    new_raw_refresh_token, new_expires_at = create_refresh_token(user_id=user.id)

    # Atomic single-use rotation guard: only one concurrent caller can claim rowcount == 1
    rotate_stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.id == record.id,
            RefreshToken.is_revoked == False,
        )
        .values(
            is_revoked=True,
            revoked_at=now,
            replaced_by_token_id=new_token_id,
        )
    )
    rotate_result = await db.execute(rotate_stmt)
    if rotate_result.rowcount != 1:
        # Concurrent refresh race or replay detected -> revoke entire token family
        await _revoke_token_family(db, record.family_id, now)
        await db.commit()
        raise UnauthorizedError("Refresh token already rotated; session revoked")

    new_token_record = RefreshToken(
        id=new_token_id,
        user_id=user.id,
        family_id=record.family_id,
        token_hash=hash_token(new_raw_refresh_token),
        is_revoked=False,
        expires_at=new_expires_at,
    )
    db.add(new_token_record)
    await db.commit()

    new_access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    """Revoke the refresh token and its entire session family on logout."""
    token_hashed = hash_token(raw_refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hashed)
    record = (await db.execute(stmt)).scalar_one_or_none()
    if not record:
        return
    now = datetime.now(timezone.utc)
    await _revoke_token_family(db, record.family_id, now)
    await db.commit()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Retrieve user by ID."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise NotFoundError("User", str(user_id))
    return user
