from __future__ import annotations

from react_assistant.agent.parser import ReActParser
from react_assistant.agent.prompts import PromptBuilder
from react_assistant.agent.react_loop import ReActLoop, ReActRunResult
from react_assistant.llm.client import OpenAICompatibleClient
from react_assistant.llm.models import ChatMessage
from react_assistant.logs.logger import ActionLogger
from react_assistant.memory.memory import ConversationMemory
from react_assistant.tools.registry import ToolRegistry


class AssistantAgent:
    def __init__(
        self,
        llm_client: OpenAICompatibleClient,
        memory: ConversationMemory,
        tools: ToolRegistry,
        prompt_builder: PromptBuilder,
        logger: ActionLogger,
        max_iterations: int,
        tool_timeout_seconds: int | None = None,
        max_scratchpad_chars: int = 12000,
    ) -> None:
        self.llm_client = llm_client
        self.memory = memory
        self.tools = tools
        self.prompt_builder = prompt_builder
        self.logger = logger
        self.max_iterations = max_iterations
        self.tool_timeout_seconds = tool_timeout_seconds
        self._parser = ReActParser()
        self._react_loop = ReActLoop(
            llm_client,
            self._parser,
            tools,
            logger,
            max_iterations,
            tool_timeout_seconds=tool_timeout_seconds,
            max_scratchpad_chars=max_scratchpad_chars,
        )

    def ask(self, user_input: str) -> ReActRunResult:
        user_input = (user_input or "").strip()
        if not user_input:
            raise ValueError("Empty prompt.")
        # Build the memory summary EXCLUDING nothing yet (current message not
        # stored), then store. This avoids sending the current message twice
        # (once in the summary, once as the user turn).
        messages = self._build_messages(user_input)
        self.memory.append("user", user_input)
        try:
            result = self._react_loop.run(messages)
        except Exception:
            # Roll back the optimistic user append? No - keep it so the user
            # can see what failed. Just re-raise.
            raise
        self.memory.append("assistant", result.final_answer)
        return result

    def _build_messages(self, user_input: str) -> list[ChatMessage]:
        # Exclude 0 trailing records because current input is not yet stored.
        # But include prior history (last 8) truncated per-record.
        memory_summary = self.memory.summary(max_messages=8)
        return self.prompt_builder.build(user_input=user_input, memory_summary=memory_summary, tools=self.tools)
