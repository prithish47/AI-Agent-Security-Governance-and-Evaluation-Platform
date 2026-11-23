# =============================================================================
# AgentGuard — Basic Tests
# =============================================================================

import pytest


def test_app_imports():
    """Verify the application module can be imported without errors."""
    from app.core.config import settings
    assert settings.app_name == "AgentGuard"


def test_config_defaults():
    """Verify default configuration values are set correctly."""
    from app.core.config import settings
    assert settings.global_iteration_ceiling == 20
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30


def test_exceptions():
    """Verify custom exceptions work correctly."""
    from app.core.exceptions import (
        NotFoundError,
        ForbiddenError,
        ConflictError,
        SecurityViolationError,
    )
    
    err = NotFoundError("Agent", "abc-123")
    assert "abc-123" in str(err)
    assert err.code == "RESOURCE_NOT_FOUND"
    
    err = ForbiddenError()
    assert err.code == "FORBIDDEN"
    
    err = ConflictError("Email already exists")
    assert err.code == "CONFLICT"
    
    err = SecurityViolationError("Approval tampered")
    assert err.code == "SECURITY_VIOLATION"
