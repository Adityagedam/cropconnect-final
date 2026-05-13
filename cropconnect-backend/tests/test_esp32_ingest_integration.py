# Integration coverage for ESP32 telemetry ingest validation.
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from routers import sensors as sensor_routes


class FakeCursor:
    def __init__(self, readings):
        self.readings = readings
        self.lastrowid = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, _sql, params=None):
        params = params or ()
        self.lastrowid = len(self.readings) + 1
        self.readings.append(params)


class FakeConnection:
    def __init__(self, readings):
        self.readings = readings

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self, **_kwargs):
        return FakeCursor(self.readings)

    def commit(self):
        return None


class Esp32IngestIntegrationTests(unittest.TestCase):
    def test_telemetry_ingest_accepts_valid_payload(self):
        readings = []

        @contextmanager
        def fake_connection():
            yield FakeConnection(readings)

        client = TestClient(app)
        with (
            patch.object(sensor_routes, "check_api_key", lambda *args, **kwargs: None),
            patch("services.sensor_service.get_connection", fake_connection),
        ):
            response = client.post(
                "/api/telemetry/ingest",
                headers={"X-API-Key": "test-key"},
                json={"device_id": "ccdev_valid", "soil_moisture": 50, "humidity": 40, "temperature": 28, "ph": 6.5},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["device_id"], "ccdev_valid")
        self.assertEqual(len(readings), 1)

    def test_telemetry_ingest_rejects_invalid_payload(self):
        client = TestClient(app)
        with patch.object(sensor_routes, "check_api_key", lambda *args, **kwargs: None):
            response = client.post(
                "/api/telemetry/ingest",
                headers={"X-API-Key": "test-key"},
                json={"device_id": "ccdev_invalid", "soil_moisture": 150},
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
