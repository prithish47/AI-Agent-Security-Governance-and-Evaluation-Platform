# =============================================================================
# AgentGuard — Ollama Local Models Provider Adapter
# =============================================================================

import json
from typing import Any, Dict, List, Optional
import httpx

from app.ai.base import AIProvider, AIResponse, ToolCallProposal
from app.core.config import settings


class OllamaProvider(AIProvider):
    """
    Ollama local models provider adapter (e.g. Llama 3, Mistral, Qwen).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model_name = model_name or settings.ollama_model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        messages = [{"role": "system", "content": system_prompt}]
        for item in conversation_history:
            if item.get("role") == "tool":
                messages.append({
                    "role": "user",
                    "content": f"Tool result for {item.get('tool_name')}: {json.dumps(item.get('result', {}))}",
                })
            else:
                messages.append(item)
        messages.append({"role": "user", "content": user_prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model_name, "messages": messages, "stream": False},
                )
                if res.status_code != 200:
                    return AIResponse(error=f"Ollama error {res.status_code}: {res.text}")

                data = res.json()
                content = data["message"]["content"]
                return AIResponse(final_answer=content)
        except Exception as exc:
            return AIResponse(error=f"Ollama connection error: {str(exc)}")
