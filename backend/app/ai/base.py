# =============================================================================
# AgentGuard — AI Provider Abstraction Interface
# =============================================================================
# COMMON ADAPTER INTERFACE:
# Isolates the rest of AgentGuard from vendor-specific AI SDKs and APIs.
# Untrusted model outputs are converted into strictly typed AIResponse objects.
# =============================================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolCallProposal:
    """A tool call proposed by an AI model."""
    tool_name: str
    arguments: Dict[str, Any]


@dataclass
class AIResponse:
    """Typed response returned from any AI provider adapter."""
    final_answer: Optional[str] = None
    tool_call: Optional[ToolCallProposal] = None
    error: Optional[str] = None

    @property
    def has_tool_call(self) -> bool:
        return self.tool_call is not None

    @property
    def has_final_answer(self) -> bool:
        return self.final_answer is not None

    @property
    def is_error(self) -> bool:
        return self.error is not None


class AIProvider(ABC):
    """Abstract Base Class for AI Model Providers."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        """
        Generate next response or tool call proposal from the model.
        Model output is treated as strictly untrusted input.
        """
        pass
