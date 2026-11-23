# =============================================================================
# AgentGuard — Custom Exceptions
# =============================================================================
# Centralized exception classes used throughout the application.
#
# WHY CUSTOM EXCEPTIONS?
# 1. Clear error types: "NotFoundError" is clearer than "Exception"
# 2. HTTP status mapping: Each exception maps to a specific HTTP status code
# 3. Consistent error responses: All errors follow the same JSON format
# 4. Separation of concerns: Business logic raises domain exceptions,
#    the API layer converts them to HTTP responses
#
# HOW IT WORKS:
# Business logic raises these exceptions → FastAPI exception handlers
# catch them → Return consistent JSON error responses to the client
# =============================================================================

from fastapi import HTTPException, status


class AgentGuardError(Exception):
    """Base exception for all AgentGuard application errors."""
    
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AgentGuardError):
    """Resource not found (HTTP 404)."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with ID {identifier} not found",
            code="RESOURCE_NOT_FOUND",
        )
        self.resource = resource
        self.identifier = identifier


class ConflictError(AgentGuardError):
    """Resource already exists or conflicts with existing data (HTTP 409)."""
    
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFLICT")


class ForbiddenError(AgentGuardError):
    """User does not have permission for this action (HTTP 403)."""
    
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message=message, code="FORBIDDEN")


class UnauthorizedError(AgentGuardError):
    """Authentication required or failed (HTTP 401)."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, code="UNAUTHORIZED")


class ValidationError(AgentGuardError):
    """Business logic validation failure (HTTP 400)."""
    
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message=message, code="VALIDATION_ERROR")
        self.field = field


class SecurityViolationError(AgentGuardError):
    """
    A security boundary was violated (HTTP 403).
    
    This is distinct from ForbiddenError — it indicates a potential attack
    or integrity violation, not just insufficient permissions.
    Examples: approval tampering, cross-tenant access, replay attack.
    """
    
    def __init__(self, message: str):
        super().__init__(message=message, code="SECURITY_VIOLATION")


class PolicyDeniedError(AgentGuardError):
    """A security policy denied the requested action."""
    
    def __init__(self, message: str, rule: str, tool_name: str):
        super().__init__(message=message, code="POLICY_DENIED")
        self.rule = rule
        self.tool_name = tool_name
