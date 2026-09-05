from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
from typing import Any

from react_assistant.utils.helpers import ensure_parent_dir, utc_now_iso


class ActionLogger:
    """Text + JSONL logger with rotation and per-instance handler binding."""

    def __init__(self, log_dir: Path, max_bytes: int = 1_000_000, backups: int = 3) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.text_log_path = self.log_dir / "assistant.log"
        self.json_log_path = self.log_dir / "actions.jsonl"
        self._lock = threading.Lock()
        # Use a unique logger per log_dir so tests / multiple runtimes
        # never write to a stale directory.
        self._logger = logging.getLogger(f"react_assistant.{self.log_dir.resolve()}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._configure_handlers(max_bytes, backups)

    def _configure_handlers(self, max_bytes: int, backups: int) -> None:
        if self._logger.handlers:
            return
        ensure_parent_dir(self.text_log_path)
        text_handler = RotatingFileHandler(
            self.text_log_path, maxBytes=max_bytes, backupCount=backups,
            encoding="utf-8",
        )
        text_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"))
        self._logger.addHandler(text_handler)
        # NOTE: no console StreamHandler on purpose - it polluted piped
        # stdout/stderr output in v0.1. CLI rendering owns the console.

    def info(self, message: str) -> None:
        self._logger.info(message)

    def _redacted(self, payload: dict[str, Any]) -> dict[str, Any]:
        redacted = {}
        for key, value in payload.items():
            lowered = key.lower()
            if any(secret in lowered for secret in ("api_key", "authorization", "token", "secret")):
                redacted[key] = "***redacted***"
            elif isinstance(value, str) and len(value) > 4000:
                redacted[key] = value[:4000] + "...[truncated in log]"
            else:
                redacted[key] = value
        return redacted

    def event(self, event_type: str, **payload: Any) -> None:
        record = {"timestamp": utc_now_iso(), "event_type": event_type, **payload}
        line = json.dumps(self._redacted(record), ensure_ascii=False)
        with self._lock:
            try:
                with self.json_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError:
                pass
        self._logger.info("%s %s", event_type, self._redacted(payload))

    def close(self) -> None:
        for handler in list(self._logger.handlers):
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
            self._logger.removeHandler(handler)
