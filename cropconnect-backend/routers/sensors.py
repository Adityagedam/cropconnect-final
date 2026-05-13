from typing import Any

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request, Response

from config import settings
from db.connections import get_connection
from logging_config import configure_logging
from models import TelemetryIn
from services.auth_service import decimal_to_float, owner_profile_context, require_auth_owner, require_sensor_read_access
from services.esp32_service import (
    active_esp32_device_key,
    check_api_key,
    esp32_device_key_summary,
    require_esp32_get_write_enabled,
    rotate_esp32_device_key,
)
from services.rate_limit import rate_limit_public_request
from services.sensor_service import (
    esp32_payload_to_telemetry,
    insert_telemetry_reading,
    latest_sensor_context,
    reading_to_sensor_list,
    telemetry_received_at,
)

AUTH_COOKIE_NAME = "cropconnect_auth"
router = APIRouter()
logger = configure_logging()


def log_backend_error(context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)


def raise_public_error(status_code: int, detail: str, context: str, exc: Exception) -> None:
    log_backend_error(context, exc)
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/api/public/sensors/latest")
def public_latest_landing_sensor(request: Request):
    rate_limit_public_request(request, "public-sensors-latest", limit=60, window_seconds=60)
    device_id = settings.public_landing_sensor_device_id
    if not device_id:
        return {
            "device_id": "",
            "source": "unavailable",
            "readings": [],
            "recorded_at": None,
            "message": "No public landing sensor is configured.",
        }

    context = latest_sensor_context(device_id)
    public_readings = [
        {key: value for key, value in reading.items() if key != "device_id"}
        for reading in context.get("readings", [])
        if isinstance(reading, dict)
    ]
    return {
        "device_id": "",
        "source": context.get("source", "unavailable"),
        "readings": public_readings,
        "recorded_at": context.get("recorded_at"),
        "message": context.get("message", ""),
    }


@router.post("/api/telemetry/ingest")
def ingest_telemetry(
    payload: TelemetryIn,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    check_api_key(x_api_key, api_key, payload.device_id)
    reading_id = insert_telemetry_reading(payload)

    return {
        "ok": True,
        "id": reading_id,
        "device_id": payload.device_id,
        "received_at": telemetry_received_at(),
    }


def ingest_telemetry_from_query(request: Request, x_api_key: str | None, api_key: str | None) -> dict[str, Any]:
    data = dict(request.query_params)
    data.pop("api_key", None)
    payload = esp32_payload_to_telemetry(data)
    check_api_key(x_api_key, api_key, payload.device_id)
    reading_id = insert_telemetry_reading(payload)
    return {
        "ok": True,
        "id": reading_id,
        "device_id": payload.device_id,
        "received_at": telemetry_received_at(),
    }


@router.get("/api/telemetry/ingest")
def ingest_telemetry_get(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    return ingest_telemetry_from_query(request, x_api_key, api_key)


@router.post("/data")
async def receive(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    try:
        data = await request.json()
    except Exception as exc:
        logger.exception("Falling back to query params after JSON parse failed: %s", exc)
        data = dict(request.query_params)

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")

    payload = esp32_payload_to_telemetry(data)
    check_api_key(x_api_key, api_key, payload.device_id)
    insert_telemetry_reading(payload)
    return {"status": "ok"}


@router.get("/data")
def receive_get(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    return ingest_telemetry_from_query(request, x_api_key, api_key)


@router.get("/api/sensors/latest")
def latest_sensors(
    device_id: str = Query(default="", max_length=80),
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    if not device_id:
        return {"device_id": "", "source": "unavailable", "readings": [], "message": "No device configured"}
    require_sensor_read_access(device_id, authorization, auth_cookie, x_api_key, api_key)

    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT
                      device_id,
                      soil_moisture,
                      humidity,
                      temperature,
                      ph,
                      nitrogen,
                      phosphorus,
                      potassium,
                      recorded_at
                    FROM sensor_readings
                    WHERE device_id = %s
                    ORDER BY recorded_at DESC, id DESC
                    LIMIT 1
                    """,
                    (device_id,),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not load latest ESP32 readings", "Sensor latest lookup failed", exc)

    if not row:
        return {"device_id": device_id, "source": "unavailable", "readings": [], "message": "No readings yet"}

    readings = reading_to_sensor_list(row)
    if not readings:
        return {
            "device_id": device_id,
            "source": "esp32",
            "recorded_at": decimal_to_float(row.get("recorded_at")),
            "readings": [],
            "message": "Latest ESP32 packet had no sensor readings",
        }

    return {
        "device_id": device_id,
        "source": "esp32",
        "recorded_at": decimal_to_float(row.get("recorded_at")),
        "readings": readings,
    }


@router.get("/api/esp32/device-key")
def get_esp32_device_key(
    response: Response,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")

    response.headers["Cache-Control"] = "no-store"
    return {
        "ok": True,
        "device_id": device_id,
        **esp32_device_key_summary(device_id),
    }


@router.post("/api/esp32/device-key")
def create_esp32_device_key(
    response: Response,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")

    response.headers["Cache-Control"] = "no-store"
    summary = esp32_device_key_summary(device_id)
    if summary.get("has_active_key"):
        return {
            "ok": True,
            "device_id": device_id,
            **summary,
            "message": "An active ESP32 device key already exists. Rotate the key to reveal a new one.",
        }
    return {
        "ok": True,
        "device_id": device_id,
        "api_key": active_esp32_device_key(device_id, create_if_missing=True),
    }


@router.post("/api/esp32/device-key/rotate")
def rotate_esp32_device_key_endpoint(
    response: Response,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")

    response.headers["Cache-Control"] = "no-store"
    return {
        "ok": True,
        "device_id": device_id,
        "api_key": rotate_esp32_device_key(device_id),
    }


@router.get("/api/sensors/history")
def sensor_history(
    device_id: str = Query(default="", max_length=80),
    limit: int = Query(default=50, ge=1, le=500),
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    require_sensor_read_access(device_id, authorization, auth_cookie, x_api_key, api_key)
    query = """
        SELECT
          id,
          device_id,
          soil_moisture,
          humidity,
          temperature,
          ph,
          nitrogen,
          phosphorus,
          potassium,
          recorded_at
        FROM sensor_readings
        WHERE device_id = %s
        ORDER BY recorded_at DESC, id DESC
        LIMIT %s
    """

    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, (device_id, limit))
                rows = cursor.fetchall()
    except Exception as exc:
        raise_public_error(503, "Could not load ESP32 reading history", "Sensor history lookup failed", exc)

    return {
        "device_id": device_id,
        "count": len(rows),
        "items": [
            {key: decimal_to_float(value) for key, value in row.items()}
            for row in rows
        ],
    }
