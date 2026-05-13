# Integration coverage for weather forecast route behavior.
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from routers import weather as weather_routes


class WeatherRouterIntegrationTests(unittest.TestCase):
    def test_weather_forecast_maps_open_meteo_payload(self):
        client = TestClient(app)

        def fake_request_json(url, *args, **kwargs):
            if "geocoding-api" in url:
                return {"results": [{"name": "Pune", "admin1": "Maharashtra", "country": "India", "latitude": 18.5, "longitude": 73.8}]}
            return {
                "current": {"temperature_2m": 29.4, "relative_humidity_2m": 61, "wind_speed_10m": 12, "pressure_msl": 1011, "weather_code": 61},
                "daily": {
                    "time": ["2026-05-13", "2026-05-14"],
                    "precipitation_probability_max": [60, 20],
                    "precipitation_sum": [3.2, 0],
                    "temperature_2m_max": [31, 32],
                    "temperature_2m_min": [24, 25],
                    "weather_code": [61, 0],
                },
            }

        with patch.object(weather_routes, "rate_limit_public_request"), patch.object(weather_routes, "request_json", side_effect=fake_request_json):
            response = client.get("/api/weather/forecast?location=Pune")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["condition"], "Rain")
        self.assertEqual(payload["location"]["name"], "Pune")
        self.assertEqual(payload["rainfall"][0]["value"], 60)

    def test_weather_forecast_requires_location(self):
        client = TestClient(app)
        with patch.object(weather_routes, "rate_limit_public_request"):
            response = client.get("/api/weather/forecast")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
