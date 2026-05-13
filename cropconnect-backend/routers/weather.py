import urllib.parse
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from http_client import request_json
from services.rate_limit import rate_limit_public_request

router = APIRouter()


def raise_public_error(status_code: int, detail: str, _context: str, exc: Exception) -> None:
    raise HTTPException(status_code=status_code, detail=detail) from exc


def weather_code_condition(value: Any) -> dict[str, str]:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return {"condition": "--", "advice": ""}

    if code == 0:
        return {"condition": "Clear", "advice": "Good field-work window if sensor readings are normal."}
    if code in {1, 2, 3}:
        return {"condition": "Cloudy", "advice": "Check humidity before spraying or fertilizer application."}
    if code in {45, 48}:
        return {"condition": "Fog", "advice": "Wait for visibility and leaf surface to improve before spraying."}
    if code in {51, 53, 55, 56, 57}:
        return {"condition": "Drizzle", "advice": "Delay spraying and review irrigation need after rainfall."}
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return {"condition": "Rain", "advice": "Pause irrigation and check drainage after the rain ends."}
    if code in {71, 73, 75, 77, 85, 86}:
        return {"condition": "Snow", "advice": "Protect sensitive crops and avoid unnecessary irrigation."}
    if code in {95, 96, 99}:
        return {"condition": "Storm", "advice": "Avoid field operations and secure pump/electrical equipment."}
    return {"condition": "--", "advice": ""}


@router.get("/api/weather/forecast")
def weather_forecast(request: Request, location: str = Query(default="", max_length=160)):
    rate_limit_public_request(request, "weather", limit=60, window_seconds=60)
    if not location:
        raise HTTPException(status_code=400, detail="location is required")
    try:
        # Geocoding using Open-Meteo (free)
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": location, "count": 1, "language": "en", "format": "json"}
        )
        geo = request_json(geo_url)
        result = (geo.get("results") or [None])[0]
        if not result and "," in location:
            city_name = location.split(",", 1)[0].strip()
            geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
                {"name": city_name, "count": 1, "language": "en", "format": "json"}
            )
            geo = request_json(geo_url)
            result = (geo.get("results") or [None])[0]
        if not result:
            raise HTTPException(status_code=404, detail="Location not found")

        # Open-Meteo provides live internet forecast data without requiring an API key.
        params = {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl,precipitation,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
            "forecast_days": 7,
            "timezone": "auto",
        }
        forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
        data = request_json(forecast_url)
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "Weather request failed", "Weather request failed", exc)

    current = data.get("current", {})
    daily = data.get("daily", {})
    days = daily.get("time", [])
    rain = daily.get("precipitation_probability_max", [])
    rain_amount = daily.get("precipitation_sum", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    daily_weather_codes = daily.get("weather_code", [])
    current_condition = weather_code_condition(current.get("weather_code"))

    def rounded_number(value: Any, digits: int = 0) -> float | int | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        rounded = round(number, digits)
        return int(rounded) if digits == 0 else rounded

    def list_number(values: list[Any], index: int, digits: int = 0) -> float | int | None:
        if index >= len(values):
            return None
        return rounded_number(values[index], digits)

    def rainfall_condition(probability: Any) -> str:
        value = rounded_number(probability)
        if value is None:
            return "--"
        if value >= 50:
            return "Rain"
        if value >= 25:
            return "Cloud"
        return "Clear"

    return {
        "ok": True,
        "source": "Open-Meteo live internet forecast",
        "requested_location": location,
        "location": {
            "name": result.get("name"),
            "admin1": result.get("admin1"),
            "country": result.get("country"),
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
        },
        "temp": rounded_number(current.get("temperature_2m")),
        "condition": current_condition["condition"],
        "advice": current_condition["advice"],
        "humidity": rounded_number(current.get("relative_humidity_2m")),
        "wind": rounded_number(current.get("wind_speed_10m")),
        "pressure": rounded_number(current.get("pressure_msl")),
        "rainfall": [
            {
                "day": "Today" if index == 0 else datetime.fromisoformat(day).strftime("%a"),
                "date": day,
                "value": list_number(rain, index),
                "mm": list_number(rain_amount, index, 1),
            }
            for index, day in enumerate(days[:7])
        ],
        "forecast": [
            {
                "day": "Today" if index == 0 else datetime.fromisoformat(day).strftime("%a"),
                "icon": weather_code_condition(daily_weather_codes[index] if index < len(daily_weather_codes) else None)["condition"],
                "high": list_number(highs, index),
                "low": list_number(lows, index),
            }
            for index, day in enumerate(days)
        ],
    }
