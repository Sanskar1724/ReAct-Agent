from __future__ import annotations

from pathlib import Path

MAX_READ_CHARS = 6000
MAX_WRITE_CHARS = 50_000
MAX_LIST_ENTRIES = 100


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _resolve(root: Path, user_path: str) -> Path:
    user_path = (user_path or "").strip().strip("`\"'").strip()
    if not user_path:
        raise ValueError("A file path is required.")
    candidate = (root / user_path).resolve() if not Path(user_path).is_absolute() else Path(user_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"Path escapes workspace root ({root}). Use a path inside it.") from None
    return candidate


class ReadFileTool:
    name = "read_file"
    description = (
        "Read a text file inside the workspace. "
        "Input: relative path, e.g. 'README.md'. Returns first ~6000 chars.")
    aliases = {"read", "cat"}

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_root()).resolve()

    def run(self, input_text: str = "") -> str:
        path = _resolve(self.root, input_text)
        if not path.exists() or not path.is_file():
            raise ValueError(f"File not found: {input_text}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ValueError(f"Cannot read file: {exc}") from exc
        if len(text) > MAX_READ_CHARS:
            text = text[: MAX_READ_CHARS - 20] + "...[truncated]"
        return f"[{path.relative_to(self.root) if path.is_relative_to(self.root) else path}]\n{text}"


class WriteFileTool:
    name = "write_file"
    description = (
        "Write text to a file inside the workspace. "
        "Input format: first line is the path, remaining lines are content. "
        "Example:\nnotes/todo.txt\\nBuy milk")
    aliases = {"write", "save"}

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_root()).resolve()

    def run(self, input_text: str = "") -> str:
        text = (input_text or "").strip("\n")
        if not text or "\n" not in text:
            raise ValueError(
                "Input must be: <path> on the first line, then file content. "
                "Example: 'notes/todo.txt\\nBuy milk'.")
        first_line, _, content = text.partition("\n")
        rel = first_line.strip().strip("`\"'").strip()
        if not rel:
            raise ValueError("Missing file path on first line.")
        if len(content) > MAX_WRITE_CHARS:
            raise ValueError(f"Content too long (max {MAX_WRITE_CHARS} chars).")
        path = _resolve(self.root, rel)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Cannot write file: {exc}") from exc
        return f"Wrote {len(content)} chars to {rel}."


class ListDirTool:
    name = "list_dir"
    description = (
        "List files in a workspace directory. Input: relative dir "
        "(empty or '.' for workspace root).")
    aliases = {"ls", "list", "dir"}

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_root()).resolve()

    def run(self, input_text: str = "") -> str:
        rel = (input_text or "").strip().strip("`\"'").strip() or "."
        path = _resolve(self.root, rel)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {rel}")
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            raise ValueError(f"Cannot list directory: {exc}") from exc
        lines = []
        for entry in entries[:MAX_LIST_ENTRIES]:
            suffix = "/" if entry.is_dir() else ""
            try:
                size = "" if entry.is_dir() else f" ({entry.stat().st_size}b)"
            except OSError:
                size = ""
            lines.append(f"{entry.name}{suffix}{size}")
        extra = f"\n...and {len(entries) - MAX_LIST_ENTRIES} more" if len(entries) > MAX_LIST_ENTRIES else ""
        return f"[{rel}] {len(entries)} entries:\n" + "\n".join(lines) + extra
