from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, default: str = "") -> str:
    try:
        if not path.exists():
            return default
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return default


def write_text(path: Path, content: str) -> None:
    ensure_parent_dir(path)
    _atomic_write_text(path, content)


def _atomic_write_text(path: Path, content: str) -> None:
    ensure_parent_dir(path)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    ensure_parent_dir(path)
    if is_dataclass(payload):
        payload = asdict(payload)
    content = json.dumps(payload, indent=2, ensure_ascii=False)
    _atomic_write_text(path, content)


def truncate_text(text: str, max_chars: int, suffix: str = "...[truncated]") -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - len(suffix))] + suffix
