# Pytest integration coverage for sensor ingest and latest-read flow with mocked DB connections.
from fastapi.testclient import TestClient

from app import app
from routers import sensors as sensor_routes


def test_sensor_ingest_and_latest_sensor_read(fake_db, monkeypatch):
    client = TestClient(app)
    device_id = "ccdev_pytest"

    def accept_test_key(x_api_key, api_key=None, device_id=None):
        return None

    monkeypatch.setattr(sensor_routes, "check_api_key", accept_test_key)

    ingest = client.post(
        "/api/telemetry/ingest",
        headers={"X-API-Key": "test-key"},
        json={
            "device_id": device_id,
            "soil_moisture": 42,
            "humidity": 61,
            "temperature": 29,
            "ph": 6.8,
            "nitrogen": 18,
            "phosphorus": 9,
            "potassium": 22,
        },
    )
    assert ingest.status_code == 200

    monkeypatch.setattr(sensor_routes, "require_sensor_read_access", lambda *args, **kwargs: None)
    latest = client.get(f"/api/sensors/latest?device_id={device_id}")
    assert latest.status_code == 200
    payload = latest.json()
    values = {reading["sensor_type"]: reading["value"] for reading in payload["readings"]}
    assert values["soil_moisture"] == 42
    assert values["ph"] == 6.8
    assert len(fake_db["readings"]) == 1
