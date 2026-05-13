# ruff: noqa: F821
from __future__ import annotations

from typing import get_type_hints

from fastapi import APIRouter, Cookie, Header, Query

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


def get_chat_history(
    user_id: int | None = Query(default=None, ge=1),
    email: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    if owner_id:
        query = """
            SELECT *
            FROM chat_messages
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT %s
        """
        values = (owner_id, limit)
    elif owner_email:
        query = """
            SELECT *
            FROM chat_messages
            WHERE email = %s
            ORDER BY id DESC
            LIMIT %s
        """
        values = (owner_email.strip().lower(), limit)
    else:
        query = """
            SELECT *
            FROM chat_messages
            WHERE email IS NULL AND user_id IS NULL
            ORDER BY id DESC
            LIMIT %s
        """
        values = (limit,)
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, values)
                rows = cursor.fetchall()
    except Exception as exc:
        raise_public_error(503, "Could not load chat history", "Chat history lookup failed", exc)

    return {
        "ok": True,
        "items": [
            {
                "id": row["id"],
                "type": "bot" if row["message_type"] == "bot" else "user",
                "text": row["text"],
                "relatedToPlantOrSoil": None if row.get("related_to_plant_or_soil") is None else bool(row["related_to_plant_or_soil"]),
                "createdAt": decimal_to_float(row.get("created_at")),
            }
            for row in reversed(rows)
        ],
    }


def save_dashboard_snapshot(
    payload: DashboardSnapshotIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    sensor_context = latest_sensor_context(device_id)
    sensor_data = sensor_context.get("sensor_data") if sensor_context.get("source") == "esp32" else {}
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dashboard_snapshots (
                      user_id, email, device_id, source, sensor_data, pump_data, timers,
                      weather_data, market_data, telemetry_packet
                    )
                    VALUES (%s, %s, %s, %s, CAST(%s AS JSON), CAST(%s AS JSON), CAST(%s AS JSON),
                            CAST(%s AS JSON), CAST(%s AS JSON), CAST(%s AS JSON))
                    """,
                    (
                        owner_id,
                        owner_email,
                        device_id,
                        sensor_context.get("source") or "unavailable",
                        json_text(sensor_data),
                        json_text(payload.pump_data),
                        json_text(payload.timers),
                        json_text(None),
                        json_text(None),
                        json_text({}),
                    ),
                )
            conn.commit()
    except Exception as exc:
        raise_public_error(503, "Could not save dashboard snapshot", "Dashboard snapshot save failed", exc)

    return {"ok": True}


def get_latest_dashboard_snapshot(
    user_id: int | None = Query(default=None, ge=1),
    email: str | None = Query(default=None, max_length=255),
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    if owner_id:
        query = """
            SELECT *
            FROM dashboard_snapshots
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 1
        """
        values = (owner_id,)
    elif owner_email:
        query = """
            SELECT *
            FROM dashboard_snapshots
            WHERE email = %s
            ORDER BY id DESC
            LIMIT 1
        """
        values = (owner_email.strip().lower(),)
    else:
        query = """
            SELECT *
            FROM dashboard_snapshots
            WHERE email IS NULL AND user_id IS NULL
            ORDER BY id DESC
            LIMIT 1
        """
        values = ()
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, values)
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not load dashboard snapshot", "Dashboard snapshot lookup failed", exc)

    if not row:
        return {"ok": True, "snapshot": None}

    return {
        "ok": True,
        "snapshot": {
            "id": row["id"],
            "device_id": row.get("device_id"),
            "source": row.get("source"),
            "sensor_data": parse_json_column(row.get("sensor_data"), {}),
            "pump_data": parse_json_column(row.get("pump_data"), {}),
            "timers": parse_json_column(row.get("timers"), {}),
            "weather_data": parse_json_column(row.get("weather_data"), None),
            "market_data": parse_json_column(row.get("market_data"), None),
            "telemetry_packet": parse_json_column(row.get("telemetry_packet"), {}),
            "created_at": decimal_to_float(row.get("created_at")),
        },
    }


def create_router(core) -> APIRouter:
    _bind_core(core)
    _resolve_route_types(get_chat_history, save_dashboard_snapshot, get_latest_dashboard_snapshot)
    router = APIRouter()
    router.add_api_route('/api/farm/chat-history', get_chat_history, methods=['GET'])
    router.add_api_route('/api/farm/snapshot', save_dashboard_snapshot, methods=['POST'])
    router.add_api_route('/api/farm/snapshot/latest', get_latest_dashboard_snapshot, methods=['GET'])
    return router
