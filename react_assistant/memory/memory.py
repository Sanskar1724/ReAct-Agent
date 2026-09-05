from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from react_assistant.llm.models import ChatMessage
from react_assistant.utils.helpers import read_json, truncate_text, utc_now_iso, write_json

_MAX_RECORD_CHARS = 2000
_SUMMARY_PER_RECORD_CHARS = 500


@dataclass(slots=True)
class MemoryRecord:
    role: str
    content: str
    timestamp: str


class ConversationMemory:
    def __init__(self, path: Path, max_records: int = 200) -> None:
        self.path = path
        self.max_records = max(10, max_records)
        self._records: list[MemoryRecord] = []
        self.load()

    def load(self) -> list[MemoryRecord]:
        raw_records = read_json(self.path, default=[])
        records: list[MemoryRecord] = []
        if isinstance(raw_records, list):
            for record in raw_records:
                if not isinstance(record, dict):
                    continue
                role = str(record.get("role", "user"))
                content = str(record.get("content", ""))
                timestamp = str(record.get("timestamp", ""))
                if role not in ("user", "assistant", "system", "tool"):
                    role = "user"
                records.append(MemoryRecord(role=role, content=content, timestamp=timestamp))
        # Keep only the tail so a huge history file never blows up RAM.
        self._records = records[-self.max_records :]
        return self._records

    def save(self) -> None:
        try:
            write_json(self.path, [asdict(record) for record in self._records])
        except OSError:
            pass

    def append(self, role: str, content: str) -> None:
        content = truncate_text(str(content), _MAX_RECORD_CHARS)
        self._records.append(MemoryRecord(
            role=role, content=content, timestamp=utc_now_iso()))
        # Enforce cap.
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]
        self.save()

    def extend(self, messages: Iterable[ChatMessage]) -> None:
        for message in messages:
            self.append(message.role, message.content)

    def as_messages(self, max_messages: int | None = None) -> list[ChatMessage]:
        records = self._records if max_messages is None else self._records[-max_messages:]
        return [ChatMessage(role=record.role, content=record.content) for record in records]

    def summary(self, max_messages: int = 8, exclude_last: int = 0) -> str:
        records = self._records[-max_messages:] if max_messages else list(self._records)
        if exclude_last and records:
            records = records[: -exclude_last] if exclude_last < len(records) else []
        if not records:
            return "No prior conversation memory."

        lines = ["Conversation memory:"]
        for record in records:
            content = truncate_text(record.content.replace("\n", " ").strip(),
                                    _SUMMARY_PER_RECORD_CHARS)
            lines.append(f"- {record.role}: {content}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Simple case-insensitive substring search over history."""
        needle = query.lower().strip()
        if not needle:
            return []
        hits = [r for r in self._records if needle in r.content.lower()]
        return hits[-limit:]

    def clear(self) -> None:
        self._records = []
        self.save()
