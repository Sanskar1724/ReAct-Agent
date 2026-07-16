from __future__ import annotations


class WeatherTool:
    name = "weather"
    description = "Return a placeholder weather response for a requested location."
    aliases = {"forecast", "weather"}

    def run(self, location: str) -> str:
        location = location.strip()
        if not location:
            raise ValueError("A location is required.")
        return (
            "Weather tool is a Phase 1 placeholder. "
            f"Requested location: {location}. Configure a weather API to return live conditions."
        )
