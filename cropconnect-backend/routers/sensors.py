# ruff: noqa: F821
from __future__ import annotations

from typing import get_type_hints

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request

AUTH_COOKIE_NAME = "cropconnect_auth"

_core = None


def _resolve_route_types(*functions):
    for func in functions:
        func.__annotations__ = get_type_hints(func, globalns=globals(), localns=globals())


def _bind_core(core):
    global _core
    _core = core
    for name in dir(core):
        if not name.startswith("__"):
            globals()[name] = getattr(core, name)


def public_latest_landing_sensor(request: Request):
    rate_limit_public_request(request, "public-sensors-latest", limit=60, window_seconds=60)
    device_id = PUBLIC_LANDING_SENSOR_DEVICE_ID
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
        "received_at": datetime.now(timezone.utc).isoformat(),
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
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


def ingest_telemetry_get(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    return ingest_telemetry_from_query(request, x_api_key, api_key)


async def receive(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    try:
        data = await request.json()
    except Exception:
        data = dict(request.query_params)

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Expected a JSON object")

    payload = esp32_payload_to_telemetry(data)
    check_api_key(x_api_key, api_key, payload.device_id)
    insert_telemetry_reading(payload)
    return {"status": "ok"}


def receive_get(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    return ingest_telemetry_from_query(request, x_api_key, api_key)


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
        raise HTTPException(
            status_code=409,
            detail="An active ESP32 device key already exists. Rotate the key to reveal a new one.",
        )
    return {
        "ok": True,
        "device_id": device_id,
        "api_key": active_esp32_device_key(device_id, create_if_missing=True),
    }


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


def reading_to_sensor_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    sensor_meta = [
        ("soil_moisture", "%"),
        ("humidity", "%"),
        ("temperature", "C"),
        ("ph", "pH"),
        ("nitrogen", "mg/kg"),
        ("phosphorus", "mg/kg"),
        ("potassium", "mg/kg"),
    ]

    return [
        {
            "sensor_type": sensor_type,
            "value": decimal_to_float(row[sensor_type]),
            "unit": unit,
            "recorded_at": decimal_to_float(row["recorded_at"]),
            "device_id": row["device_id"],
        }
        for sensor_type, unit in sensor_meta
        if row.get(sensor_type) is not None
    ]


def latest_sensor_context(device_id: str | None) -> dict[str, Any]:
    if not device_id:
        return {
            "device_id": "",
            "source": "unavailable",
            "sensor_data": {},
            "readings": [],
            "recorded_at": None,
            "message": "No sensor device is configured for this account.",
        }

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
        log_backend_error("Latest ESP32 reading lookup failed", exc)
        return {
            "device_id": device_id,
            "source": "unavailable",
            "sensor_data": {},
            "readings": [],
            "recorded_at": None,
            "message": "Could not load latest ESP32 readings.",
        }

    if not row:
        return {
            "device_id": device_id,
            "source": "unavailable",
            "sensor_data": {},
            "readings": [],
            "recorded_at": None,
            "message": "No ESP32 readings found for this device.",
        }

    readings = reading_to_sensor_list(row)
    sensor_data = {
        "soil_moisture": decimal_to_float(row.get("soil_moisture")),
        "soilMoisture": decimal_to_float(row.get("soil_moisture")),
        "humidity": decimal_to_float(row.get("humidity")),
        "temperature": decimal_to_float(row.get("temperature")),
        "ph": decimal_to_float(row.get("ph")),
        "soilPh": decimal_to_float(row.get("ph")),
        "nitrogen": decimal_to_float(row.get("nitrogen")),
        "phosphorus": decimal_to_float(row.get("phosphorus")),
        "potassium": decimal_to_float(row.get("potassium")),
    }
    return {
        "device_id": device_id,
        "source": "esp32",
        "sensor_data": sensor_data,
        "readings": readings,
        "recorded_at": decimal_to_float(row.get("recorded_at")),
        "message": "" if readings else "Latest ESP32 packet had no sensor readings.",
    }


def insert_telemetry_reading(payload: TelemetryIn) -> int:
    insert_sql = """
        INSERT INTO sensor_readings (
          device_id,
          soil_moisture,
          humidity,
          temperature,
          ph,
          nitrogen,
          phosphorus,
          potassium,
          raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
    """

    values = (
        payload.device_id,
        payload.soil_moisture,
        payload.humidity,
        payload.temperature,
        payload.ph,
        payload.nitrogen,
        payload.phosphorus,
        payload.potassium,
        payload.model_dump_json(),
    )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(insert_sql, values)
            reading_id = cursor.lastrowid
        conn.commit()

    return int(reading_id)


def first_present(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def esp32_payload_to_telemetry(data: dict[str, Any]) -> TelemetryIn:
    return TelemetryIn(
        device_id=first_present(data, "device_id", "deviceId", "device", "id") or "",
        soil_moisture=first_present(data, "soil_moisture", "soilMoisture", "moisture"),
        humidity=first_present(data, "humidity", "hum"),
        temperature=first_present(data, "temperature", "temp"),
        ph=first_present(data, "ph", "soil_ph", "soilPh"),
        nitrogen=first_present(data, "nitrogen", "n"),
        phosphorus=first_present(data, "phosphorus", "p"),
        potassium=first_present(data, "potassium", "k"),
    )


def create_router(core) -> APIRouter:
    _bind_core(core)
    _resolve_route_types(public_latest_landing_sensor, ingest_telemetry, ingest_telemetry_from_query, ingest_telemetry_get, receive, receive_get, latest_sensors, get_esp32_device_key, create_esp32_device_key, rotate_esp32_device_key_endpoint, sensor_history)
    router = APIRouter()
    router.add_api_route('/api/public/sensors/latest', public_latest_landing_sensor, methods=['GET'])
    router.add_api_route('/api/telemetry/ingest', ingest_telemetry, methods=['POST'])
    router.add_api_route('/api/telemetry/ingest', ingest_telemetry_get, methods=['GET'])
    router.add_api_route('/data', receive, methods=['POST'])
    router.add_api_route('/data', receive_get, methods=['GET'])
    router.add_api_route('/api/sensors/latest', latest_sensors, methods=['GET'])
    router.add_api_route('/api/sensors/history', sensor_history, methods=['GET'])
    router.add_api_route('/api/esp32/device-key', get_esp32_device_key, methods=['GET'])
    router.add_api_route('/api/esp32/device-key', create_esp32_device_key, methods=['POST'])
    router.add_api_route('/api/esp32/device-key/rotate', rotate_esp32_device_key_endpoint, methods=['POST'])
    return router
