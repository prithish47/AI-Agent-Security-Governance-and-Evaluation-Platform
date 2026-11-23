# =============================================================================
# AgentGuard — OpenAI-Compatible AI Provider Adapter
# =============================================================================

import json
from typing import Any, Dict, List, Optional
import httpx

from app.ai.base import AIProvider, AIResponse, ToolCallProposal
from app.core.config import settings


class OpenAIProvider(AIProvider):
    """
    OpenAI-compatible chat completion provider with tool calling support.
    Works with OpenAI, Azure OpenAI, vLLM, Groq, Together, etc.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.openai_api_key or "mock-key"
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model_name = model_name or settings.openai_model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
    ) -> AIResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = [{"role": "system", "content": system_prompt}]
        for item in conversation_history:
            if item.get("role") == "tool":
                messages.append({
                    "role": "tool",
                    "content": json.dumps(item.get("result", {})),
                    "name": item.get("tool_name", "tool"),
                })
            else:
                messages.append(item)
        messages.append({"role": "user", "content": user_prompt})

        tools_param = []
        for t in available_tools:
            tools_param.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", f"Execute {t['name']}"),
                    "parameters": t.get("schema", {"type": "object", "properties": {}}),
                },
            })

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
        }
        if tools_param:
            payload["tools"] = tools_param

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if res.status_code != 200:
                    return AIResponse(error=f"OpenAI API error {res.status_code}: {res.text}")

                data = res.json()
                choice = data["choices"][0]["message"]

                # Check if model requested a tool call
                tool_calls = choice.get("tool_calls")
                if tool_calls:
                    first_call = tool_calls[0]
                    fn_name = first_call["function"]["name"]
                    fn_args_raw = first_call["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except Exception:
                        fn_args = {}
                    return AIResponse(tool_call=ToolCallProposal(tool_name=fn_name, arguments=fn_args))

                return AIResponse(final_answer=choice.get("content") or "")
        except Exception as exc:
            return AIResponse(error=f"OpenAI connection error: {str(exc)}")
