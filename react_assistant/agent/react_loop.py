from __future__ import annotations

from dataclasses import asdict, dataclass, field

from react_assistant.agent.parser import ParsedAgentOutput, ReActParser
from react_assistant.llm.client import OpenAICompatibleClient
from react_assistant.llm.models import ChatMessage
from react_assistant.logs.logger import ActionLogger
from react_assistant.tools.registry import ToolRegistry


@dataclass(slots=True)
class ReActStep:
    iteration: int
    prompt: str
    model_output: str
    parsed: ParsedAgentOutput
    observation: str | None = None


@dataclass(slots=True)
class ReActRunResult:
    final_answer: str
    steps: list[ReActStep] = field(default_factory=list)
    usage: dict[str, int] | None = None


class ReActLoop:
    def __init__(
        self,
        llm_client: OpenAICompatibleClient,
        parser: ReActParser,
        tools: ToolRegistry,
        logger: ActionLogger,
        max_iterations: int,
        tool_timeout_seconds: int | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.parser = parser
        self.tools = tools
        self.logger = logger
        self.max_iterations = max_iterations
        self.tool_timeout_seconds = tool_timeout_seconds

    def run(self, messages: list[ChatMessage]) -> ReActRunResult:
        scratchpad = ""
        steps: list[ReActStep] = []

        for iteration in range(1, self.max_iterations + 1):
            prompt_messages = list(messages)
            if scratchpad:
                prompt_messages.append(ChatMessage(
                    role="assistant", content=scratchpad))

            self.logger.event("llm_request", iteration=iteration,
                              message_count=len(prompt_messages))
            response = self.llm_client.chat(prompt_messages)
            parsed = self.parser.parse(response.content)
            self.logger.event(
                "llm_response",
                iteration=iteration,
                output=response.content,
                usage=asdict(response.usage) if response.usage else None,
            )

            if parsed.final_answer:
                step = ReActStep(iteration=iteration, prompt=scratchpad,
                                 model_output=response.content, parsed=parsed)
                steps.append(step)
                return ReActRunResult(
                    final_answer=parsed.final_answer,
                    steps=steps,
                    usage=asdict(response.usage) if response.usage else None,
                )

            if parsed.action:
                observation = self._execute_tool(
                    parsed.action, parsed.action_input or "")
                scratchpad = self._append_to_scratchpad(
                    scratchpad, response.content, observation)
                steps.append(
                    ReActStep(
                        iteration=iteration,
                        prompt=scratchpad,
                        model_output=response.content,
                        parsed=parsed,
                        observation=observation,
                    )
                )
                continue

            step = ReActStep(iteration=iteration, prompt=scratchpad,
                             model_output=response.content, parsed=parsed)
            steps.append(step)
            return ReActRunResult(
                final_answer=response.content.strip(),
                steps=steps,
                usage=asdict(response.usage) if response.usage else None,
            )

        raise RuntimeError(
            f"Reached max iterations ({self.max_iterations}) without a final answer.")

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        self.logger.event("tool_request", tool_name=tool_name,
                          tool_input=tool_input)
        try:
            result = self.tools.execute(
                tool_name, tool_input, timeout_seconds=self.tool_timeout_seconds
            )
        except Exception as exc:
            observation = f"Tool error: {exc}"
            self.logger.event(
                "tool_error", tool_name=tool_name, error=str(exc))
            return observation

        self.logger.event(
            "tool_result", tool_name=result.tool_name, output=result.output_text)
        return result.output_text

    def _append_to_scratchpad(self, scratchpad: str, model_output: str, observation: str) -> str:
        fragments = [
            fragment.strip()
            for fragment in [scratchpad, model_output, f"Observation: {observation}"]
            if fragment and fragment.strip()
        ]
        return "\n".join(fragments).strip()
