from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass
from typing import Protocol


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


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RunnableTool] = {}
        self._aliases: dict[str, str] = {}

    def register(self, tool: RunnableTool) -> None:
        self._tools[tool.name] = tool
        for alias in tool.aliases:
            self._aliases[alias.lower()] = tool.name

    def names(self) -> list[str]:
        return sorted(self._tools)

    def descriptions(self) -> list[str]:
        return [f"{tool.name}: {tool.description}" for tool in self._tools.values()]

    def resolve(self, tool_name: str) -> RunnableTool:
        lookup = tool_name.lower().strip()
        canonical_name = self._aliases.get(lookup, lookup)
        if canonical_name not in self._tools:
            raise KeyError(f"Unknown tool: {tool_name}")
        return self._tools[canonical_name]

    def execute(
        self, tool_name: str, input_text: str = "", timeout_seconds: int | None = None
    ) -> ToolExecutionResult:
        tool = self.resolve(tool_name)
        try:
            if timeout_seconds and timeout_seconds > 0:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(tool.run, input_text)
                    output_text = future.result(timeout=timeout_seconds)
            else:
                output_text = tool.run(input_text)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Tool '{tool.name}' exceeded timeout of {timeout_seconds}s."
            ) from None
        return ToolExecutionResult(
            tool_name=tool.name, input_text=input_text, output_text=output_text
        )
