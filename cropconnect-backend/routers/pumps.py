# ruff: noqa: F821
from __future__ import annotations

from typing import get_type_hints

from fastapi import APIRouter, Cookie, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

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


def esp32_relay_command(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
    device_id: str = Query(default="", max_length=80),
):
    if not device_id.strip():
        raise HTTPException(status_code=400, detail="device_id is required")
    check_api_key(x_api_key, api_key, device_id)
    states = sync_relay_commands_from_db(device_id)
    return relay_command_text(states)


def esp32_relay_command_short(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
    device_id: str = Query(default="", max_length=80),
):
    return esp32_relay_command(x_api_key, api_key, device_id)


def parse_relay_states(values: dict[str, Any]) -> dict[int, bool]:
    states: dict[int, bool] = {}
    for relay_key, raw_value in values.items():
        key = str(relay_key).lower().strip()
        if key in {"api_key", "device_id"}:
            continue
        if key.startswith("relay"):
            key = key.replace("relay", "", 1)
        if key.startswith("r"):
            key = key[1:]
        try:
            relay_number = int(key)
        except ValueError:
            continue
        value_text = str(raw_value).lower().strip()
        states[relay_number] = value_text in {"1", "true", "on", "yes", "high"}
    return states


def esp32_relay_status(
    payload: RelayStatusIn,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    check_api_key(x_api_key, api_key, payload.device_id)
    states = parse_relay_states(payload.relays)

    save_relay_applied_states_to_db(payload.device_id, states)
    desired_states = sync_relay_commands_from_db(payload.device_id)
    return {
        "ok": True,
        "device_id": payload.device_id,
        "status": relay_status_payload_from_db(payload.device_id, desired_states),
    }


def esp32_relay_status_update(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    device_id = str(request.query_params.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    check_api_key(x_api_key, api_key, device_id)
    states = parse_relay_states(dict(request.query_params))
    save_relay_applied_states_to_db(device_id, states)
    desired_states = sync_relay_commands_from_db(device_id)
    return {"ok": True, "status": relay_status_payload_from_db(device_id, desired_states)}


def get_esp32_relay_status(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
    device_id: str = Query(default="", max_length=80),
):
    if not device_id.strip():
        raise HTTPException(status_code=400, detail="device_id is required")
    check_api_key(x_api_key, api_key, device_id)
    desired_states = sync_relay_commands_from_db(device_id)
    return {"ok": True, "status": relay_status_payload_from_db(device_id, desired_states)}


def set_pump_state(
    payload: PumpStateIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    requested_device_id = str(payload.device_id or "").strip()
    if not owner_device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")
    if requested_device_id and requested_device_id != owner_device_id:
        raise HTTPException(status_code=403, detail="Pump device does not belong to this account")
    device_id = owner_device_id
    state = "on" if payload.on else "off"
    message = "Pump command saved in MySQL. The main ESP32 will fetch it over SIM800L and forward it to the pump ESP32."

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pump_states (
                      user_id, email, device_id, pump_id, is_on, runtime_minutes, schedule, sent_to_esp32, message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s)
                    """,
                    (
                        owner_id,
                        owner_email,
                        device_id,
                        payload.pump_id,
                        1 if payload.on else 0,
                        payload.runtime or 0,
                        json_text(payload.schedule),
                        0,
                        message,
                    ),
                )
            conn.commit()
    except Exception as exc:
        raise_public_error(503, "Could not queue pump command", "Pump command queue failed", exc)

    return {
        "ok": True,
        "device_id": device_id,
        "pump_id": payload.pump_id,
        "state": state,
        "sent_to_esp32": False,
        "queued_for_sim800l": True,
        "message": message,
        "esp32": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_pump_state(
    payload: PumpStateSaveIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    requested_device_id = str(payload.device_id or "").strip()
    if not owner_device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")
    if requested_device_id and requested_device_id != owner_device_id:
        raise HTTPException(status_code=403, detail="Pump device does not belong to this account")
    device_id = owner_device_id
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pump_states (
                      user_id, email, device_id, pump_id, is_on, runtime_minutes, schedule, sent_to_esp32, message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s)
                    """,
                    (
                        owner_id,
                        owner_email,
                        device_id,
                        payload.pump_id,
                        1 if payload.on else 0,
                        payload.runtime or 0,
                        json_text(payload.schedule),
                        1 if payload.sent_to_esp32 else 0,
                        payload.message or "",
                    ),
                )
            conn.commit()
    except Exception as exc:
        raise_public_error(503, "Could not save pump state", "Pump state save failed", exc)

    return {"ok": True, "device_id": device_id}


def get_pump_states(
    user_id: int | None = Query(default=None, ge=1),
    email: str | None = Query(default=None, max_length=255),
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not device_id:
        return {"ok": True, "items": []}
    if owner_id:
        query = """
            SELECT ps.*
            FROM pump_states ps
            INNER JOIN (
              SELECT pump_id, MAX(id) AS latest_id
              FROM pump_states
              WHERE user_id = %s AND device_id = %s
              GROUP BY pump_id
            ) latest ON ps.id = latest.latest_id
            WHERE ps.device_id = %s
            ORDER BY ps.pump_id
        """
        values = (owner_id, device_id, device_id)
    elif owner_email:
        query = """
            SELECT ps.*
            FROM pump_states ps
            INNER JOIN (
              SELECT pump_id, MAX(id) AS latest_id
              FROM pump_states
              WHERE email = %s AND device_id = %s
              GROUP BY pump_id
            ) latest ON ps.id = latest.latest_id
            WHERE ps.device_id = %s
            ORDER BY ps.pump_id
        """
        values = (owner_email.strip().lower(), device_id, device_id)
    else:
        query = """
            SELECT ps.*
            FROM pump_states ps
            INNER JOIN (
              SELECT pump_id, MAX(id) AS latest_id
              FROM pump_states
              WHERE email IS NULL AND user_id IS NULL AND device_id = %s
              GROUP BY pump_id
            ) latest ON ps.id = latest.latest_id
            WHERE ps.device_id = %s
            ORDER BY ps.pump_id
        """
        values = (device_id, device_id)
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, values)
                rows = cursor.fetchall()
    except Exception as exc:
        raise_public_error(503, "Could not load pump states", "Pump states lookup failed", exc)

    active_timer_pumps = active_timer_pump_ids_from_db(device_id)
    relay_status = latest_relay_applied_status_from_db(device_id)
    applied_relays = relay_status.get("applied", {})
    items = []
    seen_pump_ids = set()
    for row in rows:
        pump_id = row["pump_id"]
        seen_pump_ids.add(pump_id)
        timer_active = pump_id in active_timer_pumps
        relay_number = pump_id_to_relay_number(pump_id)
        desired_on = bool(row["is_on"]) or timer_active
        applied_on = applied_relays.get(relay_number) if 1 <= relay_number <= 8 else None
        items.append(
            {
                "pump_id": pump_id,
                "on": desired_on,
                "desired_on": desired_on,
                "applied_on": applied_on,
                "hardware_confirmed": applied_on is not None and applied_on == desired_on,
                "runtime": int(row.get("runtime_minutes") or 0),
                "schedule": parse_json_column(row.get("schedule"), {}),
                "sent_to_esp32": bool(row.get("sent_to_esp32")),
                "message": "Pump is inside an active backend timer window" if timer_active else (row.get("message") or ""),
                "timer_active": timer_active,
                "applied_updated_at": relay_status.get("updated_at"),
                "updated_at": decimal_to_float(row.get("created_at")),
            }
        )
    for pump_id in sorted(active_timer_pumps - seen_pump_ids):
        items.append(
            {
                "pump_id": pump_id,
                "on": True,
                "desired_on": True,
                "applied_on": applied_relays.get(pump_id_to_relay_number(pump_id)),
                "hardware_confirmed": applied_relays.get(pump_id_to_relay_number(pump_id)) is True,
                "runtime": 0,
                "schedule": {},
                "sent_to_esp32": False,
                "message": "Pump is inside an active backend timer window",
                "timer_active": True,
                "applied_updated_at": relay_status.get("updated_at"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {
        "ok": True,
        "items": items,
    }


def save_pump_timers(
    payload: PumpTimersSaveIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                if owner_id:
                    cursor.execute(
                        "DELETE FROM pump_timers WHERE user_id = %s AND (device_id = %s OR device_id IS NULL)",
                        (owner_id, device_id),
                    )
                elif owner_email:
                    cursor.execute(
                        "DELETE FROM pump_timers WHERE email = %s AND (device_id = %s OR device_id IS NULL)",
                        (owner_email.strip().lower(), device_id),
                    )
                else:
                    cursor.execute(
                        "DELETE FROM pump_timers WHERE email IS NULL AND user_id IS NULL AND (device_id = %s OR device_id IS NULL)",
                        (device_id,),
                    )
                for pump_id, timers in payload.timers.items():
                    for timer in timers:
                        start_time = format_timer_start_time(timer.get("startTime"))
                        try:
                            duration_minutes = int(timer.get("duration") or 0)
                        except (TypeError, ValueError):
                            raise HTTPException(status_code=400, detail="Timer duration must be a number") from None
                        if not start_time:
                            raise HTTPException(status_code=400, detail="Timer start time is invalid")
                        if duration_minutes < 1 or duration_minutes > 480:
                            raise HTTPException(status_code=400, detail="Timer duration must be between 1 and 480 minutes")
                        cursor.execute(
                            """
                            INSERT INTO pump_timers (
                              user_id, email, device_id, pump_id, timer_key, start_time, duration_minutes, days, active
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s)
                            """,
                            (
                                owner_id,
                                owner_email,
                                device_id,
                                str(pump_id),
                                str(timer.get("id") or f"{pump_id}-{timer.get('startTime')}"),
                                start_time,
                                duration_minutes,
                                json_text(timer.get("days") or []),
                                1,
                            ),
                        )
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(503, "Could not save timers", "Timer save failed", exc)

    return {"ok": True}


def get_pump_timers(
    user_id: int | None = Query(default=None, ge=1),
    email: str | None = Query(default=None, max_length=255),
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if owner_id:
        query = """
            SELECT *
            FROM pump_timers
            WHERE user_id = %s AND active = 1
              AND (%s = '' OR device_id = %s OR device_id IS NULL)
            ORDER BY pump_id, start_time
        """
        values = (owner_id, device_id, device_id)
    elif owner_email:
        query = """
            SELECT *
            FROM pump_timers
            WHERE email = %s AND active = 1
              AND (%s = '' OR device_id = %s OR device_id IS NULL)
            ORDER BY pump_id, start_time
        """
        values = (owner_email.strip().lower(), device_id, device_id)
    else:
        query = """
            SELECT *
            FROM pump_timers
            WHERE email IS NULL AND user_id IS NULL AND active = 1
              AND (%s = '' OR device_id = %s OR device_id IS NULL)
            ORDER BY pump_id, start_time
        """
        values = (device_id, device_id)
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, values)
                rows = cursor.fetchall()
    except Exception as exc:
        raise_public_error(503, "Could not load timers", "Timer lookup failed", exc)

    timers: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        timers.setdefault(row["pump_id"], []).append(
            {
                "id": row["timer_key"],
                "startTime": format_timer_start_time(row.get("start_time")),
                "duration": int(row["duration_minutes"]),
                "days": parse_json_column(row.get("days"), []),
            }
        )

    return {"ok": True, "timers": timers}


def pump_id_to_relay_number(pump_id: Any) -> int:
    try:
        return int("".join(ch for ch in str(pump_id) if ch.isdigit()) or 0)
    except ValueError:
        return 0


def parse_timer_start_minutes(value: Any) -> int | None:
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60) % (24 * 60)
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return int(value.hour) * 60 + int(value.minute)

    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except (TypeError, ValueError):
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def format_timer_start_time(value: Any) -> str:
    start_minute = parse_timer_start_minutes(value)
    if start_minute is None:
        return ""
    return f"{start_minute // 60:02d}:{start_minute % 60:02d}"


def timer_row_is_active(row: dict[str, Any], now: datetime | None = None) -> bool:
    start_minute = parse_timer_start_minutes(row.get("start_time"))
    try:
        duration = int(row.get("duration_minutes") or 0)
    except (TypeError, ValueError):
        return False
    if start_minute is None or duration < 1:
        return False

    days = parse_json_column(row.get("days"), [])
    if not isinstance(days, list) or not days:
        days = [0, 1, 2, 3, 4, 5, 6]

    now = now or datetime.now(FARM_TIMER_TIMEZONE)
    current_day = (now.weekday() + 1) % 7
    current_minute = now.hour * 60 + now.minute
    for day in days:
        try:
            timer_day = int(day)
        except (TypeError, ValueError):
            continue
        if timer_day < 0 or timer_day > 6:
            continue
        offset_days = (current_day - timer_day + 7) % 7
        minutes_since_start = offset_days * 1440 + current_minute - start_minute
        if 0 <= minutes_since_start < duration:
            return True
    return False


def active_timer_pump_ids_from_db(device_id: str) -> set[str]:
    device = device_id.strip()
    if not device:
        return set()

    query = """
        SELECT pump_id, start_time, duration_minutes, days
        FROM pump_timers
        WHERE device_id = %s AND active = 1
    """
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, (device,))
                rows = cursor.fetchall() or []
    except Exception as exc:
        raise_public_error(503, "Could not load pump timers", "Pump timer lookup failed", exc)

    now = datetime.now(FARM_TIMER_TIMEZONE)
    return {str(row.get("pump_id") or "") for row in rows if timer_row_is_active(row, now)}


def latest_relay_command_states_from_db(device_id: str) -> dict[int, bool]:
    device_id = device_id.strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required for relay commands")
    states = {index: False for index in range(1, 9)}
    query = """
        SELECT ps.pump_id, ps.is_on
        FROM pump_states ps
        INNER JOIN (
          SELECT pump_id, MAX(id) AS latest_id
          FROM pump_states
          WHERE device_id = %s
          GROUP BY pump_id
        ) latest ON ps.id = latest.latest_id
        WHERE ps.device_id = %s
    """

    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, (device_id, device_id))
                rows = cursor.fetchall()
    except Exception as exc:
        raise_public_error(503, "Could not load relay commands", "Relay command lookup failed", exc)

    for row in rows:
        relay_number = pump_id_to_relay_number(row["pump_id"])
        if 1 <= relay_number <= 8:
            states[relay_number] = bool(row["is_on"])

    for pump_id in active_timer_pump_ids_from_db(device_id):
        relay_number = pump_id_to_relay_number(pump_id)
        if 1 <= relay_number <= 8:
            states[relay_number] = True

    return states


def sync_relay_commands_from_db(device_id: str) -> dict[int, bool]:
    return latest_relay_command_states_from_db(device_id)


def save_relay_applied_states_to_db(device_id: str, states: dict[int, bool]) -> None:
    device = str(device_id or "").strip()
    if not device or not states:
        return
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                for relay_number, is_on in states.items():
                    if 1 <= int(relay_number) <= 8:
                        cursor.execute(
                            """
                            INSERT INTO relay_statuses (device_id, relay_number, is_on, reported_at)
                            VALUES (%s, %s, %s, UTC_TIMESTAMP())
                            ON DUPLICATE KEY UPDATE
                              is_on = VALUES(is_on),
                              reported_at = UTC_TIMESTAMP()
                            """,
                            (device, int(relay_number), 1 if is_on else 0),
                        )
            conn.commit()
    except Exception as exc:
        raise_public_error(503, "Could not save relay status", "Relay status save failed", exc)


def latest_relay_applied_status_from_db(device_id: str) -> dict[str, Any]:
    device = str(device_id or "").strip()
    applied = {index: None for index in range(1, 9)}
    latest_reported_at = None
    if not device:
        return {"applied": applied, "updated_at": latest_reported_at}
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT relay_number, is_on, reported_at
                    FROM relay_statuses
                    WHERE device_id = %s
                    """,
                    (device,),
                )
                rows = cursor.fetchall() or []
    except Exception as exc:
        raise_public_error(503, "Could not load relay status", "Relay status lookup failed", exc)

    for row in rows:
        relay_number = int(row.get("relay_number") or 0)
        if 1 <= relay_number <= 8:
            applied[relay_number] = bool(row.get("is_on"))
            reported_at = row.get("reported_at")
            if reported_at and (latest_reported_at is None or reported_at > latest_reported_at):
                latest_reported_at = reported_at
    return {"applied": applied, "updated_at": decimal_to_float(latest_reported_at)}


def relay_status_payload_from_db(device_id: str, desired_states: dict[int, bool] | None = None) -> dict[str, Any]:
    desired = desired_states or {index: False for index in range(1, 9)}
    applied_status = latest_relay_applied_status_from_db(device_id)
    return {
        "desired": {
            str(relay_number): bool(desired.get(relay_number, False))
            for relay_number in range(1, 9)
        },
        "applied": {
            str(relay_number): applied_status["applied"].get(relay_number)
            for relay_number in range(1, 9)
        },
        "updated_at": applied_status.get("updated_at"),
    }


def create_router(core) -> APIRouter:
    _bind_core(core)
    _resolve_route_types(esp32_relay_command, esp32_relay_command_short, parse_relay_states, esp32_relay_status, esp32_relay_status_update, get_esp32_relay_status, set_pump_state, save_pump_state, get_pump_states, save_pump_timers, get_pump_timers)
    router = APIRouter()
    router.add_api_route('/api/esp32/relay-command', esp32_relay_command, methods=['GET'], response_class=PlainTextResponse)
    router.add_api_route('/esp32/relay-command', esp32_relay_command_short, methods=['GET'], response_class=PlainTextResponse)
    router.add_api_route('/api/esp32/relay-status', esp32_relay_status, methods=['POST'])
    router.add_api_route('/api/esp32/relay-status/update', esp32_relay_status_update, methods=['GET'])
    router.add_api_route('/api/esp32/relay-status', get_esp32_relay_status, methods=['GET'])
    router.add_api_route('/api/pump/state', set_pump_state, methods=['POST'])
    router.add_api_route('/api/farm/pump-state', save_pump_state, methods=['POST'])
    router.add_api_route('/api/farm/pump-states', get_pump_states, methods=['GET'])
    router.add_api_route('/api/farm/timers', save_pump_timers, methods=['POST'])
    router.add_api_route('/api/farm/timers', get_pump_timers, methods=['GET'])
    return router
