# =============================================================================
# AgentGuard — Authentication Endpoints
# =============================================================================

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.auth import service as auth_service
from app.auth.rbac import get_current_user
from app.auth.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    TokenRefresh,
    UserResponse,
)
from app.persistence.models import User
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(register_in: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account with Argon2id password hashing."""
    return await auth_service.register_user(db, register_in)


@router.post("/login", response_model=TokenResponse)
async def login(login_in: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive access + refresh tokens."""
    user = await auth_service.authenticate_user(db, login_in)
    return await auth_service.create_tokens_for_user(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_in: TokenRefresh, db: AsyncSession = Depends(get_db)):
    """Refresh access token using valid refresh token."""
    return await auth_service.refresh_access_token(db, refresh_in.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(refresh_in: TokenRefresh, db: AsyncSession = Depends(get_db)):
    """Revoke refresh token on user logout."""
    await auth_service.revoke_refresh_token(db, refresh_in.refresh_token)
    return MessageResponse(message="Successfully logged out and revoked refresh token")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return current_user
