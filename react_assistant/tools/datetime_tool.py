from __future__ import annotations

from datetime import datetime, timezone


class DateTimeTool:
    name = "datetime"
    description = "Return the current date and time in UTC."
    aliases = {"time", "datetime", "now"}

    def run(self, _: str = "") -> str:
        return datetime.now(timezone.utc).isoformat()
