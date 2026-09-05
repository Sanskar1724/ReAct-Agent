from __future__ import annotations

import atexit
import concurrent.futures
from dataclasses import dataclass
from typing import Protocol

MAX_TOOL_INPUT_CHARS = 8000
MAX_TOOL_OUTPUT_CHARS = 8000


class RunnableTool(Protocol):
    name: str
    description: str
    aliases: set[str]

    def run(self, input_text: str = "") -> str:
        ...


@dataclass(slots=True)
class ToolExecutionResult:
    tool_name: str
    input_text: str
    output_text: str


# Shared pool so every tool call does not pay thread-creation cost.
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool")
atexit.register(_POOL.shutdown, False)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RunnableTool] = {}
        self._aliases: dict[str, str] = {}

    def register(self, tool: RunnableTool) -> None:
        name = str(tool.name).strip()
        if not name:
            raise ValueError("Tool must have a non-empty name.")
        key = name.lower()
        if key in self._tools:
            raise ValueError(f"Duplicate tool name: {name}")
        self._tools[key] = tool
        # Canonical name always resolves.
        self._aliases[key] = key
        for alias in (tool.aliases or set()):
            alias_key = str(alias).lower().strip()
            if not alias_key or alias_key == key:
                continue
            if alias_key in self._aliases and self._aliases[alias_key] != key:
                raise ValueError(
                    f"Alias collision: '{alias}' already maps to "
                    f"'{self._aliases[alias_key]}', cannot reuse for '{name}'.")
            self._aliases[alias_key] = key

    def names(self) -> list[str]:
        return sorted(tool.name for tool in self._tools.values())

    def descriptions(self) -> list[str]:
        return [f"{tool.name}: {tool.description}" for tool in self._tools.values()]

    def resolve(self, tool_name: str) -> RunnableTool:
        lookup = str(tool_name or "").lower().strip()
        canonical_name = self._aliases.get(lookup, lookup)
        tool = self._tools.get(canonical_name)
        if tool is None:
            available = ", ".join(self.names()) or "none"
            raise KeyError(f"Unknown tool: {tool_name}. Available: {available}")
        return tool

    def execute(
        self, tool_name: str, input_text: str = "", timeout_seconds: int | None = None
    ) -> ToolExecutionResult:
        tool = self.resolve(tool_name)
        input_text = str(input_text or "")
        if len(input_text) > MAX_TOOL_INPUT_CHARS:
            raise ValueError(
                f"Tool input too long ({len(input_text)} chars, "
                f"max {MAX_TOOL_INPUT_CHARS}).")
        try:
            if timeout_seconds and timeout_seconds > 0:
                future = _POOL.submit(tool.run, input_text)
                try:
                    output_text = future.result(timeout=timeout_seconds)
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    raise TimeoutError(
                        f"Tool '{tool.name}' exceeded timeout of {timeout_seconds}s."
                    ) from None
            else:
                output_text = tool.run(input_text)
        except (TimeoutError, KeyError, ValueError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Tool '{tool.name}' failed: {exc}") from exc
        output_text = str(output_text if output_text is not None else "")
        if len(output_text) > MAX_TOOL_OUTPUT_CHARS:
            output_text = output_text[: MAX_TOOL_OUTPUT_CHARS - 20] + "...[truncated]"
        return ToolExecutionResult(
            tool_name=tool.name, input_text=input_text, output_text=output_text
        )
