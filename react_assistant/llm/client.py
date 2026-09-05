from __future__ import annotations

import json
import time
from urllib import error, request
from typing import Sequence

from .models import ChatMessage, LLMResponse, LLMUsage


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        use_mock: bool = False,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        temperature: float = 0.2,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.use_mock = use_mock
        self.timeout_seconds = max(5, timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.temperature = temperature

    def chat(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        if self.use_mock:
            return self._mock_response(messages)
        if not self.api_key:
            raise RuntimeError(
                "API key is not configured and mock mode is disabled. "
                "Set OPENROUTER_API_KEY or LLM_USE_MOCK=1.")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.temperature,
        }
        encoded = json.dumps(payload).encode("utf-8")

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            http_request = request.Request(
                url=url,
                data=encoded,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "react_assistant/0.2.0",
                    # Required by OpenRouter for analytics; harmless elsewhere.
                    "HTTP-Referer": "https://github.com/react-assistant",
                    "X-Title": "ReAct Assistant",
                },
                method="POST",
            )
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except error.HTTPError as exc:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:2000]
                except Exception:
                    detail = ""
                # Retry on rate-limit / transient 5xx, not on 401/403/400.
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    last_error = exc
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise RuntimeError(
                    f"LLM request failed: {exc.code} {exc.reason}: {detail}") from exc
            except (error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise RuntimeError(f"LLM request failed: {exc}") from exc
        else:
            raise RuntimeError(f"LLM request failed after retries: {last_error}")

        try:
            choices = raw.get("choices") or []
            message = (choices[0].get("message") or {}) if choices else {}
            content = message.get("content")
            # Some reasoning models return None content with reasoning field.
            if content is None:
                content = message.get("reasoning") or message.get("reasoning_content") or ""
            content = str(content or "").strip()
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {raw!r:.500}") from exc
        if not content:
            raise RuntimeError("LLM returned an empty response.")
        usage_payload = raw.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=_safe_token(usage_payload.get("prompt_tokens")),
            completion_tokens=_safe_token(usage_payload.get("completion_tokens")),
            total_tokens=_safe_token(usage_payload.get("total_tokens")),
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


def _safe_token(value: object) -> int | None:
    try:
        if value is None:
            return None
        number = int(value)  # type: ignore[arg-type]
        return number if number >= 0 else None
    except (ValueError, TypeError):
        return None
