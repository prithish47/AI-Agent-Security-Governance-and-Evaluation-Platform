# =============================================================================
# AgentGuard — Common Schemas
# =============================================================================

from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated list response wrapper."""
    model_config = ConfigDict(from_attributes=True)

    items: List[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """Simple confirmation or message response."""
    message: str
