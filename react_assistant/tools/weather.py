from __future__ import annotations

import json
from urllib import error, parse, request


_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle", 61: "light rain",
    63: "rain", 65: "heavy rain", 66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers",
    85: "light snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail", 99: "thunderstorm with hail",
}


def _get_json(url: str, timeout: int = 15) -> dict:
    req = request.Request(url, headers={"User-Agent": "react_assistant/0.2.0"}, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


class WeatherTool:
    name = "weather"
    description = (
        "Get current weather for a location (e.g. 'Paris', 'Delhi'). "
        "Uses Open-Meteo, no API key needed.")
    aliases = {"forecast"}

    def run(self, location: str) -> str:
        location = (location or "").strip().strip("`\"'").strip()
        if not location:
            raise ValueError("A location is required, e.g. 'weather' input 'Paris'.")
        if len(location) > 120:
            raise ValueError("Location name too long.")
        try:
            geo_url = f"{_GEOCODE_URL}?{parse.urlencode({'name': location, 'count': 1, 'language': 'en', 'format': 'json'})}"
            geo = _get_json(geo_url)
            results = geo.get("results") or []
            if not results:
                return f"Could not geocode location: {location}. Try 'City, Country'."
            place = results[0]
            lat, lon = place.get("latitude"), place.get("longitude")
            place_name = place.get("name", location)
            country = place.get("country", "")
            forecast_url = (
                f"{_FORECAST_URL}?{parse.urlencode({'latitude': lat, 'longitude': lon, 'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m', 'timezone': 'auto'})}"
            )
            forecast = _get_json(forecast_url)
            current = forecast.get("current") or {}
            temp = current.get("temperature_2m", "?")
            feels = current.get("apparent_temperature", "?")
            humidity = current.get("relative_humidity_2m", "?")
            wind = current.get("wind_speed_10m", "?")
            code = current.get("weather_code")
            desc = _WEATHER_CODES.get(code, f"code {code}") if code is not None else "unknown"
            where = f"{place_name}, {country}".strip(", ")
            return (
                f"Weather in {where}: {desc}, {temp}C "
                f"(feels {feels}C), humidity {humidity}%, wind {wind} km/h."
            )
        except (error.URLError, TimeoutError, OSError) as exc:
            return f"Weather lookup failed (network): {exc}"
        except Exception as exc:
            return f"Weather lookup failed: {exc}"
