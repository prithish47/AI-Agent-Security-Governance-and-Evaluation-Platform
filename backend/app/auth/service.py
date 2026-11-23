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
    """Generate JWT access token and persist hashed refresh token in database."""
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
    )
    raw_refresh_token, expires_at = create_refresh_token(user_id=user.id)

    # Store hashed refresh token in DB
    token_record = RefreshToken(
        user_id=user.id,
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


async def refresh_access_token(db: AsyncSession, raw_refresh_token: str) -> TokenResponse:
    """Validate refresh token and issue a new access token."""
    token_hashed = hash_token(raw_refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hashed)
    record = (await db.execute(stmt)).scalar_one_or_none()

    if not record or record.is_revoked:
        raise UnauthorizedError("Invalid or revoked refresh token")

    now = datetime.now(timezone.utc)
    if record.expires_at.tzinfo is None:
        record_exp = record.expires_at.replace(tzinfo=timezone.utc)
    else:
        record_exp = record.expires_at

    if record_exp < now:
        raise UnauthorizedError("Refresh token has expired")

    # Fetch user
    user = (await db.execute(select(User).where(User.id == record.user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User account is not active")

    new_access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        username=user.username,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    """Revoke refresh token on logout."""
    token_hashed = hash_token(raw_refresh_token)
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hashed)
        .values(is_revoked=True)
    )
    await db.execute(stmt)
    await db.commit()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Retrieve user by ID."""
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise NotFoundError("User", str(user_id))
    return user
