# =============================================================================
# AgentGuard — API v1 Router
# =============================================================================
# Aggregates all domain API endpoint routers.
# =============================================================================

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.agents import router as agents_router
from app.api.v1.endpoints.tools import router as tools_router
from app.api.v1.endpoints.policies import router as policies_router
from app.api.v1.endpoints.executions import router as executions_router
from app.api.v1.endpoints.approvals import router as approvals_router
from app.api.v1.endpoints.audit import router as audit_router

api_router = APIRouter()

# Register domain routers
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(agents_router)
api_router.include_router(tools_router)
api_router.include_router(policies_router)
api_router.include_router(executions_router)
api_router.include_router(approvals_router)
api_router.include_router(audit_router)


@api_router.get("/", tags=["System"])
async def api_root():
    """API v1 root status endpoint."""
    return {
        "api": "AgentGuard",
        "version": "v1",
        "status": "operational",
    }
