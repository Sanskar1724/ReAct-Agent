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
        )

    def ask(self, user_input: str) -> ReActRunResult:
        self.memory.append("user", user_input)
        messages = self._build_messages(user_input)
        result = self._react_loop.run(messages)
        self.memory.append("assistant", result.final_answer)
        return result

    def _build_messages(self, user_input: str) -> list[ChatMessage]:
        memory_summary = self.memory.summary()
        return self.prompt_builder.build(user_input=user_input, memory_summary=memory_summary, tools=self.tools)
