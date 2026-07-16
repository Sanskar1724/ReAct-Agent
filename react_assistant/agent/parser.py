from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedAgentOutput:
    thought: str | None = None
    action: str | None = None
    action_input: str | None = None
    final_answer: str | None = None
    raw_text: str = ""


class ReActParser:
    def parse(self, text: str) -> ParsedAgentOutput:
        thought = self._extract_block(text, "Thought")
        action = self._extract_line(text, "Action")
        action_input = self._extract_block(text, "Action Input")
        final_answer = self._extract_block(text, "Final Answer")

        if final_answer is None and text.strip() and "final answer" not in text.lower() and action is None:
            final_answer = text.strip()

        return ParsedAgentOutput(
            thought=thought,
            action=action,
            action_input=action_input,
            final_answer=final_answer,
            raw_text=text,
        )

    def _extract_line(self, text: str, label: str) -> str | None:
        prefix = f"{label}:"
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith(prefix.lower()):
                value = stripped[len(prefix):].strip()
                return value or None
        return None

    def _extract_block(self, text: str, label: str) -> str | None:
        prefix = f"{label}:"
        lines = text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith(prefix.lower()):
                first_line = stripped[len(prefix):].strip()
                remainder = [first_line] if first_line else []
                for next_line in lines[index + 1:]:
                    if next_line.strip().lower().startswith(("thought:", "action:", "final answer:", "observation:")):
                        break
                    remainder.append(next_line)
                content = "\n".join(
                    part for part in remainder if part is not None).strip()
                return content or None
        return None
