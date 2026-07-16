from __future__ import annotations

import json
from urllib import error, request
from typing import Sequence

from .models import ChatMessage, LLMResponse, LLMUsage


class OpenAICompatibleClient:
    def __init__(self, api_key: str | None, base_url: str, model: str, use_mock: bool = False) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.use_mock = use_mock

    def chat(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        if self.use_mock:
            return self._mock_response(messages)
        if not self.api_key:
            raise RuntimeError(
                "API key is not configured and mock mode is disabled.")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": 0.2,
        }
        encoded = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            url=url,
            data=encoded,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "react_assistant/0.1.0",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=60) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LLM request failed: {exc.code} {exc.reason}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        content = raw["choices"][0]["message"]["content"]
        usage_payload = raw.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=usage_payload.get("prompt_tokens"),
            completion_tokens=usage_payload.get("completion_tokens"),
            total_tokens=usage_payload.get("total_tokens"),
        )
        return LLMResponse(content=content, raw=raw, usage=usage)

    def _mock_response(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        user_messages = [
            message.content for message in messages if message.role == "user"]
        latest = user_messages[-1] if user_messages else ""
        content = (
            "Thought: I am running in mock mode because no API key is configured.\n"
            "Final Answer: "
            f"I received your message: {latest or 'an empty prompt'}. Configure OPENROUTER_API_KEY to use a live model."
        )
        return LLMResponse(
            content=content,
            raw={"mock": True},
            usage=LLMUsage(prompt_tokens=0,
                           completion_tokens=0, total_tokens=0),
        )
