# =============================================================================
# AgentGuard — Database Configuration
# =============================================================================
# Sets up the SQLAlchemy async engine and session factory.
#
# WHY ASYNC?
# When a web request queries the database, the server thread is blocked
# waiting for the database to respond. With async, the server can handle
# other requests while waiting. This matters when you have many concurrent
# users — the server stays responsive instead of queuing requests.
#
# KEY CONCEPTS:
# - Engine: The connection pool manager. One per application.
# - Session: A conversation with the database. One per request.
# - Base: The parent class for all SQLAlchemy models.
#
# HOW SESSIONS WORK:
# Each API request gets its own session via the get_db() dependency.
# The session is automatically closed when the request finishes.
# This prevents connection leaks and ensures transactions are managed.
# =============================================================================

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# =============================================================================
# Engine
# =============================================================================
# The engine manages a pool of database connections.
# 
# pool_size: Maximum number of persistent connections (default: 5)
# max_overflow: Extra connections allowed when pool is full (default: 10)
# echo: If True, logs every SQL statement (useful for debugging)
# =============================================================================

_engine_kwargs: dict = {"echo": settings.debug}  # Log SQL in debug mode — disable in production
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_async_engine(
    settings.database_url,
    **_engine_kwargs,
)


# =============================================================================
# Session Factory
# =============================================================================
# async_sessionmaker creates a factory that produces new sessions.
# 
# expire_on_commit=False means that after committing, we can still read
# the objects we just saved without hitting the database again.
# This is important for returning created objects in API responses.
# =============================================================================

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# Base Model
# =============================================================================
# All SQLAlchemy models inherit from this class.
# It provides the __tablename__ and column mapping infrastructure.
# =============================================================================

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# =============================================================================
# Database Session Dependency
# =============================================================================
# This is a FastAPI dependency that provides a database session for each
# request. It's used like this in endpoint functions:
#
#   @router.get("/items")
#   async def get_items(db: AsyncSession = Depends(get_db)):
#       ...
#
# The `async with` block ensures the session is always closed, even if
# the request handler throws an exception. This prevents connection leaks.
# =============================================================================

async def get_db():
    """
    FastAPI dependency that yields an async database session.
    
    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(MyModel))
            ...
    
    The session is automatically closed when the request completes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
