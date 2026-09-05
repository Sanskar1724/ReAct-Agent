from __future__ import annotations

from dataclasses import asdict, dataclass, field

from react_assistant.agent.parser import ParsedAgentOutput, ReActParser
from react_assistant.llm.client import OpenAICompatibleClient
from react_assistant.llm.models import ChatMessage
from react_assistant.logs.logger import ActionLogger
from react_assistant.tools.registry import ToolRegistry
from react_assistant.utils.helpers import truncate_text


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
    truncated: bool = False


def _add_usage(total: dict[str, int], usage: dict[str, int] | None) -> dict[str, int]:
    if not usage:
        return total
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value > 0:
            total[key] = total.get(key, 0) + value
    return total


class ReActLoop:
    def __init__(
        self,
        llm_client: OpenAICompatibleClient,
        parser: ReActParser,
        tools: ToolRegistry,
        logger: ActionLogger,
        max_iterations: int,
        tool_timeout_seconds: int | None = None,
        max_scratchpad_chars: int = 12000,
    ) -> None:
        self.llm_client = llm_client
        self.parser = parser
        self.tools = tools
        self.logger = logger
        self.max_iterations = max(1, max_iterations)
        self.tool_timeout_seconds = tool_timeout_seconds
        self.max_scratchpad_chars = max_scratchpad_chars

    def run(self, messages: list[ChatMessage]) -> ReActRunResult:
        scratchpad = ""
        steps: list[ReActStep] = []
        total_usage: dict[str, int] = {}
        seen_actions: set[str] = set()

        for iteration in range(1, self.max_iterations + 1):
            prompt_messages = list(messages)
            if scratchpad:
                prompt_messages.append(ChatMessage(
                    role="assistant", content=scratchpad))

            self.logger.event("llm_request", iteration=iteration,
                              message_count=len(prompt_messages))
            try:
                response = self.llm_client.chat(prompt_messages)
            except RuntimeError as exc:
                # Surface LLM failures as a graceful answer instead of a crash.
                self.logger.event("llm_error", iteration=iteration, error=str(exc)[:1000])
                final = (
                    f"I couldn't reach the language model: {exc}\n"
                    f"Partial reasoning so far:\n{scratchpad[-1000:] if scratchpad else '(none)'}"
                )
                return ReActRunResult(final_answer=final.strip(), steps=steps,
                                      usage=total_usage or None, truncated=True)
            if response.usage is not None:
                total_usage = _add_usage(total_usage, asdict(response.usage))
            parsed = self.parser.parse(response.content or "")
            self.logger.event(
                "llm_response",
                iteration=iteration,
                output=(response.content or "")[:4000],
                usage=asdict(response.usage) if response.usage else None,
            )

            if parsed.final_answer and not parsed.action:
                step = ReActStep(iteration=iteration, prompt=scratchpad,
                                 model_output=response.content, parsed=parsed)
                steps.append(step)
                return ReActRunResult(
                    final_answer=parsed.final_answer,
                    steps=steps,
                    usage=total_usage or None,
                )

            if parsed.action:
                action_key = f"{parsed.action.lower()}::{(parsed.action_input or '').strip().lower()}"
                if action_key in seen_actions:
                    observation = (
                        f"Tool error: '{parsed.action}' with the same input was already "
                        f"tried. Try a different input or give a Final Answer.")
                    self.logger.event("tool_loop_detected", tool_name=parsed.action)
                else:
                    seen_actions.add(action_key)
                    observation = self._execute_tool(
                        parsed.action, parsed.action_input or "")
                    # Truncate very long observations so the scratchpad stays bounded.
                    observation = truncate_text(observation, 2000)
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
                # If model emitted both Action and Final Answer, prefer to
                # continue the loop (tool result may still be needed), but if
                # this was the last iteration, fall through to truncation.
                continue

            # Neither action nor final answer: treat raw output as answer.
            step = ReActStep(iteration=iteration, prompt=scratchpad,
                             model_output=response.content, parsed=parsed)
            steps.append(step)
            fallback = (parsed.final_answer or (response.content or "").strip()
                        or "(empty model response)")
            return ReActRunResult(
                final_answer=fallback,
                steps=steps,
                usage=total_usage or None,
            )

        # Graceful truncation instead of raising: return best-effort answer.
        last_thought = next(
            (s.parsed.thought for s in reversed(steps) if s.parsed.thought), "")
        final = (
            f"I reached the step limit ({self.max_iterations}) without a final answer. "
            f"Here is what I found so far:\n{scratchpad[-1500:] if scratchpad else last_thought}"
        ).strip()
        self.logger.event("max_iterations_reached", max_iterations=self.max_iterations)
        return ReActRunResult(final_answer=final, steps=steps,
                              usage=total_usage or None, truncated=True)

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        self.logger.event("tool_request", tool_name=tool_name,
                          tool_input=tool_input[:2000])
        try:
            result = self.tools.execute(
                tool_name, tool_input, timeout_seconds=self.tool_timeout_seconds
            )
        except Exception as exc:
            observation = f"Tool error: {exc}"
            self.logger.event(
                "tool_error", tool_name=tool_name, error=str(exc)[:1000])
            return observation

        self.logger.event(
            "tool_result", tool_name=result.tool_name, output=result.output_text[:4000])
        return result.output_text

    def _append_to_scratchpad(self, scratchpad: str, model_output: str, observation: str) -> str:
        fragments = [
            fragment.strip()
            for fragment in [scratchpad, model_output, f"Observation: {observation}"]
            if fragment and fragment.strip()
        ]
        combined = "\n".join(fragments).strip()
        if len(combined) > self.max_scratchpad_chars:
            # Keep the tail (most recent reasoning) — most relevant.
            combined = "...[earlier reasoning truncated]...\n" + combined[-self.max_scratchpad_chars:]
        return combined
