# =============================================================================
# AgentGuard Backend — FastAPI Application Entry Point
# =============================================================================
# This is the main entry point for the AgentGuard backend.
#
# WHAT THIS FILE DOES:
# 1. Creates the FastAPI application instance
# 2. Configures CORS (Cross-Origin Resource Sharing) so the frontend can
#    communicate with the backend from a different port
# 3. Registers all API routers (endpoint groups)
# 4. Provides a health check endpoint
#
# HOW TO RUN:
#   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#
# The --reload flag enables auto-restart when code changes (dev only).
# =============================================================================

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1.router import api_router

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("agentguard")


# =============================================================================
# Application Lifespan
# =============================================================================
# FastAPI's lifespan context manager runs code at startup and shutdown.
# We use it to log startup info and verify the database connection.
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on application startup and shutdown.
    
    Startup:
      - Log application info
      - Verify database connectivity
    
    Shutdown:
      - Dispose database engine (close connection pool)
    """
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS origins: {settings.cors_origins}")
    
    # Verify database connectivity by attempting a simple connection
    try:
        async with engine.begin() as conn:
            await conn.execute(
                # A simple query that works on any PostgreSQL installation
                __import__("sqlalchemy").text("SELECT 1")
            )
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # We still start the app — the health endpoint will report unhealthy
    
    yield  # Application runs here
    
    # Shutdown: clean up the database connection pool
    await engine.dispose()
    logger.info("Application shutdown complete")


# =============================================================================
# Create FastAPI Application
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI Agent Security and Reliability Platform. "
        "AgentGuard provides a centralized security and governance layer "
        "between AI agents and the tools they execute."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    # Only show docs in debug mode for production safety
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# =============================================================================
# CORS Middleware
# =============================================================================
# CORS (Cross-Origin Resource Sharing) is a browser security feature.
# Since our frontend (port 3000) and backend (port 8000) are on different
# origins, the browser blocks requests by default. This middleware tells
# the browser "it's okay, the frontend is allowed to talk to me."
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["*"],     # Allow all HTTP methods
    allow_headers=["*"],     # Allow all headers
)


# =============================================================================
# Health Check Endpoint
# =============================================================================
# This endpoint is NOT behind authentication — it's used by:
# - Docker health checks to know if the container is healthy
# - Load balancers to know if the server can receive traffic
# - Developers to quickly verify the backend is running
#
# It checks database connectivity without exposing sensitive information.
# =============================================================================

@app.get("/health", tags=["System"])
async def health_check():
    """
    Application health check.
    
    Returns the application status and database connectivity.
    Does not require authentication.
    Does not expose sensitive information.
    """
    db_status = "connected"
    
    try:
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": settings.app_version,
        "database": db_status,
    }


# =============================================================================
# Register API Routers
# =============================================================================
# All API endpoints are organized under /api/v1/ using FastAPI's router system.
# Each domain (auth, projects, agents, etc.) gets its own router file.
# =============================================================================

app.include_router(api_router, prefix="/api/v1")
