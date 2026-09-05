from __future__ import annotations

import sys
import threading
import time


def _safe_write(text: str) -> None:
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("ascii", errors="replace").decode("ascii"))
    sys.stdout.flush()


class Spinner:
    """Lightweight terminal spinner shown during blocking operations.

    Uses a background thread so the label animates while the caller blocks.
    Falls back to a single status line when stdout is not a TTY. The spinner
    stops automatically when the context manager exits. All writes are
    Windows cp1252-safe.
    """

    _FRAMES = ["|", "/", "-", "\\"]

    def __init__(self, message: str, *, console=None, interval: float = 0.08) -> None:
        from react_assistant.cli.console import Console

        self.message = message
        self.console = console or Console()
        self.interval = interval
        self._active = False
        self._frame_index = 0
        self._thread: threading.Thread | None = None

    def _animate(self) -> None:
        while self._active:
            if sys.stdout.isatty():
                symbol = self._FRAMES[self._frame_index % len(self._FRAMES)]
                _safe_write(f"\r{self.console.cyan(symbol)} {self.message}")
                self._frame_index += 1
            time.sleep(self.interval)

    def _render_static(self) -> None:
        if sys.stdout.isatty():
            return
        _safe_write(f"{self.console.gray('...')} {self.message}\n")

    def _clear(self) -> None:
        if sys.stdout.isatty():
            _safe_write("\r" + " " * (len(self.message) + 4) + "\r")

    def __enter__(self) -> "Spinner":
        self._active = True
        if sys.stdout.isatty():
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()
        else:
            self._render_static()
        return self

    def update(self, message: str) -> None:
        self.message = message
        if sys.stdout.isatty() and self._active:
            self._clear()
            symbol = self._FRAMES[self._frame_index % len(self._FRAMES)]
            _safe_write(f"\r{self.console.cyan(symbol)} {self.message}")

    def __exit__(self, exc_type, exc, tb) -> None:
        self._active = False
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 2)
            self._thread = None
        self._clear()
