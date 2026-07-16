from __future__ import annotations

import os
import sys
from typing import Any


class Console:
    """Minimal, dependency-free terminal styling and layout helper.

    Gracefully degrades to plain text when stdout is not a TTY or when
    NO_COLOR is set in the environment.
    """

    def __init__(self, use_color: bool | None = None) -> None:
        if use_color is None:
            use_color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
        self.use_color = use_color

    # --- low level styling ------------------------------------------------
    def _wrap(self, code: str, text: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def italic(self, text: str) -> str:
        return self._wrap("3", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def blue(self, text: str) -> str:
        return self._wrap("34", text)

    def magenta(self, text: str) -> str:
        return self._wrap("35", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def gray(self, text: str) -> str:
        return self._wrap("90", text)

    # --- higher level output ---------------------------------------------
    def print(self, *args: Any, **kwargs: Any) -> None:
        print(*args, **kwargs)

    def rule(self, title: str = "", char: str = "─", width: int = 60) -> None:
        if title:
            label = f" {title} "
            pad = max(0, width - len(label))
            left = pad // 2
            right = pad - left
            line = char * left + label + char * right
        else:
            line = char * width
        print(self.gray(line))

    def panel(self, title: str, body: str, *, border: str = "│") -> None:
        lines = body.splitlines() or [""]
        width = max((len(line) for line in lines), default=0)
        print(self.gray(f"┌─ {title} " + "─" * max(0, width - len(title) - 1) + "┐"))
        for line in lines:
            print(self.gray(border) + " " + line + " " +
                  self.gray(border))
        print(self.gray("└" + "─" * (width + 2) + "┘"))

    def key_value(self, pairs: list[tuple[str, str]], key_color=None) -> None:
        key_fn = key_color or self.cyan
        for key, value in pairs:
            print(f"  {key_fn(self.bold(key))}: {value}")

    def success(self, text: str) -> None:
        print(self.green("✔ ") + text)

    def warn(self, text: str) -> None:
        print(self.yellow("⚠ ") + text)

    def error(self, text: str) -> None:
        print(self.red("✖ ") + text)

    def info(self, text: str) -> None:
        print(self.blue("ℹ ") + text)

    def status(self, text: str) -> None:
        print(self.gray("… ") + self.dim(text))
