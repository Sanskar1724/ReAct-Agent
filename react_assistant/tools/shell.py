from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

MAX_OUTPUT_CHARS = 4000
_BLOCKED_TOKENS = {
    "rm -rf /", "mkfs", ":(){", "shutdown", "reboot", "halt",
    "del /f /s /q c:", "format c:",
}


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class ShellTool:
    name = "shell"
    description = (
        "Run a shell command in the workspace (timeout-guarded). "
        "Input: command, e.g. 'python --version' or 'dir'. "
        "Destructive commands are blocked.")
    aliases = {"run", "exec", "cmd"}

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_root()).resolve()

    def run(self, input_text: str = "") -> str:
        cmd = (input_text or "").strip()
        if not cmd:
            raise ValueError("A command is required, e.g. 'python --version'.")
        if len(cmd) > 1000:
            raise ValueError("Command too long (max 1000 chars).")
        lowered = cmd.lower()
        for blocked in _BLOCKED_TOKENS:
            if blocked in lowered:
                raise ValueError(f"Blocked dangerous command pattern: {blocked!r}")
        try:
            completed = subprocess.run(
                cmd, shell=True, cwd=str(self.root), capture_output=True,
                text=True, timeout=15, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("Shell command timed out after 15s.") from None
        except OSError as exc:
            raise ValueError(f"Shell failed: {exc}") from exc
        output = ((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")).strip()
        if not output:
            output = f"(exit {completed.returncode}, no output)"
        else:
            output = f"(exit {completed.returncode})\n{output}"
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[: MAX_OUTPUT_CHARS - 20] + "...[truncated]"
        return output


class PythonExecTool:
    name = "python_exec"
    description = (
        "Execute a short Python snippet and return stdout/result. "
        "Input: Python code, e.g. 'print(2+2)'. Stdlib only, 10s limit, "
        "no file/network writes outside workspace.")
    aliases = {"python", "py", "code"}

    def run(self, input_text: str = "") -> str:
        code = (input_text or "").strip().strip("`").strip()
        if not code:
            raise ValueError("Python code is required, e.g. 'print(2+2)'.")
        if len(code) > 6000:
            raise ValueError("Code too long (max 6000 chars).")
        # Strip a single markdown python fence if present.
        if code.startswith("python\n"):
            code = code[len("python\n"):]
        wrapper = (
            "import sys\n"
            "def _main():\n"
        )
        indented = "\n".join("    " + line if line.strip() else "" for line in code.splitlines())
        # If the snippet is a bare expression, print its value.
        bare_expression = len(code.splitlines()) == 1 and not any(
            kw in code for kw in ("=", "import", "def ", "for ", "while ", "print", "return"))
        if bare_expression:
            wrapper += f"    print(repr({code}))\n"
        else:
            wrapper += indented + "\n"
        wrapper += "_main()\n"
        try:
            completed = subprocess.run(
                ["python", "-c", wrapper], capture_output=True, text=True,
                timeout=10, encoding="utf-8", errors="replace",
            )
        except FileNotFoundError:
            raise ValueError("Python interpreter not found.") from None
        except subprocess.TimeoutExpired:
            raise TimeoutError("Python snippet timed out after 10s.") from None
        output = ((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")).strip()
        if not output:
            output = f"(exit {completed.returncode}, no output)"
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[: MAX_OUTPUT_CHARS - 20] + "...[truncated]"
        _ = shlex  # keep import meaningful for future arg parsing
        return output
