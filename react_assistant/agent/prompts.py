from __future__ import annotations

from pathlib import Path

from react_assistant.llm.models import ChatMessage
from react_assistant.tools.registry import ToolRegistry
from react_assistant.utils.helpers import read_text


class PromptBuilder:
    def __init__(self, system_prompt_path: Path) -> None:
        self.system_prompt_path = system_prompt_path
        self._cached_template: str | None = None
        self._cached_mtime: float | None = None

    def _load_template(self) -> str:
        try:
            mtime = self.system_prompt_path.stat().st_mtime
        except OSError:
            return self._default_prompt()
        if self._cached_template is None or self._cached_mtime != mtime:
            self._cached_template = read_text(
                self.system_prompt_path, default=self._default_prompt())
            self._cached_mtime = mtime
        return self._cached_template or self._default_prompt()

    def build(self, user_input: str, memory_summary: str, tools: ToolRegistry, scratchpad: str = "") -> list[ChatMessage]:
        system_prompt = self._load_template()
        tool_lines = "\n".join(
            f"- {description}" for description in tools.descriptions())
        context_parts = [
            system_prompt.strip(),
            "",
            "Available tools:",
            tool_lines or "- No tools registered.",
            "",
            (memory_summary or "").strip(),
        ]
        if scratchpad.strip():
            context_parts.extend(
                ["", "Previous reasoning:", scratchpad.strip()])

        return [
            ChatMessage(role="system", content="\n".join(
                part for part in context_parts if part is not None).strip()),
            ChatMessage(role="user", content=user_input.strip()),
        ]

    def _default_prompt(self) -> str:
        return (
            "You are a professional ReAct assistant.\n"
            "Follow this format exactly when reasoning internally:\n"
            "Thought: ...\n"
            "Action: tool_name\n"
            "Action Input: tool input\n"
            "Observation: tool output\n"
            "Final Answer: ...\n"
            "If no tool is needed, answer directly with Final Answer."
        )
