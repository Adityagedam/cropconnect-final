# Sensor telemetry persistence and read-model helpers.
from datetime import datetime, timezone
from typing import Any

from db.connections import get_connection
from logging_config import configure_logging
from models import TelemetryIn
from services.auth_service import decimal_to_float

logger = configure_logging()


def log_backend_error(context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)


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


def telemetry_received_at() -> str:
    return datetime.now(timezone.utc).isoformat()
