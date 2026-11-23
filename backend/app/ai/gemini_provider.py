# =============================================================================
# AgentGuard — Google Gemini Provider Adapter
# =============================================================================

import json
from typing import Any, Dict, List, Optional
import httpx

from app.ai.base import AIProvider, AIResponse, ToolCallProposal
from app.core.config import settings


class GeminiProvider(AIProvider):
    """
    Google Gemini Generative Language API adapter.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.gemini_api_key or "mock-key"
        self.model_name = model_name or settings.gemini_model or "gemini-pro"
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        # Build contents structure
        contents = [{"role": "user", "parts": [{"text": f"System: {system_prompt}\nUser: {user_prompt}"}]}]
        for item in conversation_history:
            if item.get("role") == "tool":
                contents.append({
                    "role": "model",
                    "parts": [{"text": f"Tool '{item.get('tool_name')}' result: {json.dumps(item.get('result', {}))}"}],
                })

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.endpoint}?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": contents},
                )
                if res.status_code != 200:
                    return AIResponse(error=f"Gemini API error {res.status_code}: {res.text}")

                data = res.json()
                candidate = data["candidates"][0]["content"]
                text = candidate["parts"][0]["text"]
                return AIResponse(final_answer=text)
        except Exception as exc:
            return AIResponse(error=f"Gemini connection error: {str(exc)}")
