from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ParsedAgentOutput:
    thought: str | None = None
    action: str | None = None
    action_input: str | None = None
    final_answer: str | None = None
    raw_text: str = ""


_STOP_LABELS = ("thought:", "action:", "action input:", "final answer:", "observation:")

_FENCE_RE = re.compile(r"```(?:\w+)?\s*(.*?)```", re.DOTALL)


class ReActParser:
    def parse(self, text: str) -> ParsedAgentOutput:
        text = (text or "").strip()
        # Unwrap a single markdown code fence if the model wrapped its answer.
        fence_match = _FENCE_RE.search(text)
        if fence_match and fence_match.group(1).strip():
            # Only unwrap when the fence contains ReAct labels.
            inner = fence_match.group(1).strip()
            if any(label in inner.lower() for label in ("thought:", "action:", "final answer:")):
                text = inner

        thought = self._extract_block(text, "Thought")
        action = self._extract_line(text, "Action")
        action_input = self._extract_block(text, "Action Input")
        final_answer = self._extract_block(text, "Final Answer")

        # Guard: "Action Input:" also starts with "action" textually, so make
        # sure _extract_line("Action") did not capture the input line.
        if action and action.lower().startswith("input:"):
            action = None

        # A model-hallucinated Observation is never trustworthy; the real
        # observation always comes from tool execution. Drop it from thought
        # blocks so it cannot poison the scratchpad display.
        if final_answer is None and text and "final answer" not in text.lower() and action is None:
            # Strip any hallucinated scaffolding lines before treating rest as answer.
            cleaned = self._strip_scaffolding(text)
            final_answer = cleaned.strip() or None

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
            stripped = line.strip().strip("`").strip()
            if stripped.lower().startswith(prefix.lower()):
                # Avoid matching "Action Input:" when looking for "Action:".
                rest = stripped[len(prefix):]
                if label.lower() == "action" and rest.strip().lower().startswith("input:"):
                    continue
                value = rest.strip()
                # Action must be a single token (tool name); cut trailing prose.
                if label.lower() == "action" and value:
                    value = value.split()[0].strip("`\"',.")
                return value or None
        return None

    def _extract_block(self, text: str, label: str) -> str | None:
        prefix = f"{label}:"
        lines = text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith(prefix.lower()):
                # Skip "Action:" when searching for "Action Input:" ambiguity:
                # require exact label prefix match.
                if label.lower() == "action" and stripped.lower().startswith("action input:"):
                    continue
                first_line = stripped[len(prefix):].strip().strip("`").strip()
                remainder = [first_line] if first_line else []
                for next_line in lines[index + 1:]:
                    lowered = next_line.strip().lower()
                    if lowered.startswith(_STOP_LABELS):
                        break
                    remainder.append(next_line)
                content = "\n".join(
                    part for part in remainder if part is not None).strip().strip("`").strip()
                return content or None
        return None

    @staticmethod
    def _strip_scaffolding(text: str) -> str:
        kept = []
        for line in text.splitlines():
            if line.strip().lower().startswith(_STOP_LABELS + ("observation :",)):
                # Keep the content after the label if any (e.g. "Thought: hi").
                _, _, after = line.partition(":")
                if after.strip():
                    kept.append(after.strip())
                continue
            kept.append(line)
        return "\n".join(kept).strip()
