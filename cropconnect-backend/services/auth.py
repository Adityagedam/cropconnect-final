# ruff: noqa: F821
from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Response

from security_crypto import sign_auth_token, verify_auth_token

_core = None


def _bind_core(core) -> None:
    global _core
    _core = core
    for name in dir(core):
        if not name.startswith("__"):
            globals()[name] = getattr(core, name)


def user_row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
    email = row["email"]
    name = decrypt_text(row.get("name")) or email.split("@")[0]
    phone = decrypt_text(row.get("phone")) or ""
    state = decrypt_text(row.get("state")) or ""
    location = decrypt_text(row.get("location")) or ""
    location_type = row.get("location_type") or "city"
    district = decrypt_text(row.get("district")) or ""
    city = decrypt_text(row.get("city")) or (location if location_type == "city" else "")
    village = decrypt_text(row.get("village")) or (location if location_type == "village" else "")
    return {
        "id": row["id"],
        "email": email,
        "name": name,
        "phone": phone,
        "state": state,
        "location": location,
        "locationType": location_type,
        "district": district,
        "city": city,
        "village": village,
        "landSize": decimal_to_float(row.get("land size")),
        "sensorDeviceId": row.get("sensor_device_id") or "",
        "sensors": row.get("sensors") or "0",
        "pumps": row.get("pumps") or "0",
        "sensorSetupComplete": bool(row.get("sensor_setup_complete")),
        "sensorSetupStatus": row.get("sensor_setup_status") or "pending",
    }


def set_auth_cookie(response: Response, token: str) -> str:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )
    csrf_token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, csrf_token)
    return csrf_token


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=False,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    cookie_options = {
        "path": "/",
        "secure": AUTH_COOKIE_SECURE,
        "samesite": AUTH_COOKIE_SAMESITE,
    }
    response.delete_cookie(AUTH_COOKIE_NAME, **cookie_options)
    response.delete_cookie(CSRF_COOKIE_NAME, **cookie_options)


def auth_token_from_request(authorization: str | None, auth_cookie: str | None) -> str:
    if auth_cookie:
        return auth_cookie.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return ""


def require_auth_owner(authorization: str | None, auth_cookie: str | None = None) -> tuple[int, str]:
    token = auth_token_from_request(authorization, auth_cookie)
    if not token:
        raise HTTPException(status_code=401, detail="Login token is required")

    payload = verify_auth_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Login token is invalid or expired")
    try:
        owner_id = int(payload.get("user_id") or 0)
    except (TypeError, ValueError):
        owner_id = 0
    owner_email = str(payload.get("email") or "").strip().lower()
    if owner_id < 1 or not owner_email:
        raise HTTPException(status_code=401, detail="Login token is missing account ownership")
    return owner_id, owner_email


def require_sensor_read_access(
    device_id: str,
    authorization: str | None,
    auth_cookie: str | None,
    x_api_key: str | None = None,
    api_key: str | None = None,
) -> None:
    if api_key_matches(x_api_key, api_key, device_id):
        return

    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not owner_device_id or owner_device_id != device_id:
        raise HTTPException(status_code=403, detail="Sensor device does not belong to this account")


def auth_token_for_user(user: dict[str, Any]) -> str:
    return sign_auth_token({"user_id": user["id"], "email": user["email"]})
