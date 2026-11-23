# =============================================================================
# AgentGuard — API v1 Router
# =============================================================================
# This router aggregates all v1 API endpoint groups.
#
# As we implement each phase, we'll add more routers here:
# - auth_router (Phase 4)
# - projects_router (Phase 2)
# - agents_router (Phase 2)
# - tools_router (Phase 2)
# - policies_router (Phase 2)
# - executions_router (Phase 5)
# - approvals_router (Phase 6)
# - evaluations_router (Phase 8)
# - audit_router (Phase 2)
# =============================================================================

from fastapi import APIRouter

api_router = APIRouter()


# ---------------------------------------------------------------------------
# Placeholder endpoint to verify API routing works
# This will be replaced with real endpoints in Phase 2+
# ---------------------------------------------------------------------------

@api_router.get("/", tags=["System"])
async def api_root():
    """API v1 root — confirms the API is accessible."""
    return {
        "api": "AgentGuard",
        "version": "v1",
        "status": "operational",
    }
