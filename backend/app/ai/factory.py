# =============================================================================
# AgentGuard — AI Provider Factory
# =============================================================================

from typing import Optional
from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.ollama_provider import OllamaProvider


def get_ai_provider(
    provider_name: str,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> AIProvider:
    """
    Factory creating configured AI model adapters based on provider identifier.
    """
    name = (provider_name or "mock").lower().strip()
    if name == "openai":
        return OpenAIProvider(api_key=api_key, base_url=base_url, model_name=model_name)
    elif name == "gemini":
        return GeminiProvider(api_key=api_key, model_name=model_name)
    elif name == "ollama":
        return OllamaProvider(base_url=base_url, model_name=model_name)
    else:
        return MockAIProvider()
