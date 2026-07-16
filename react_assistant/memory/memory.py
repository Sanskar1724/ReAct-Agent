from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from react_assistant.llm.models import ChatMessage
from react_assistant.utils.helpers import read_json, utc_now_iso, write_json


@dataclass(slots=True)
class MemoryRecord:
    role: str
    content: str
    timestamp: str


class ConversationMemory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: list[MemoryRecord] = []
        self.load()

    def load(self) -> list[MemoryRecord]:
        raw_records = read_json(self.path, default=[])
        self._records = [
            MemoryRecord(
                role=record.get("role", "user"),
                content=record.get("content", ""),
                timestamp=record.get("timestamp", ""),
            )
            for record in raw_records
        ]
        return self._records

    def save(self) -> None:
        write_json(self.path, [asdict(record) for record in self._records])

    def append(self, role: str, content: str) -> None:
        self._records.append(MemoryRecord(
            role=role, content=content, timestamp=utc_now_iso()))
        self.save()

    def extend(self, messages: Iterable[ChatMessage]) -> None:
        for message in messages:
            self.append(message.role, message.content)

    def as_messages(self, max_messages: int | None = None) -> list[ChatMessage]:
        records = self._records if max_messages is None else self._records[-max_messages:]
        return [ChatMessage(role=record.role, content=record.content) for record in records]

    def summary(self, max_messages: int = 8) -> str:
        records = self._records[-max_messages:]
        if not records:
            return "No prior conversation memory."

        lines = ["Conversation memory:"]
        for record in records:
            lines.append(f"- {record.role}: {record.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        self._records = []
        self.save()
