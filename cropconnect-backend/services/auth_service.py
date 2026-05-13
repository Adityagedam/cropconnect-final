# Authentication, profile, token, cookie, and chat-record helpers.
import hashlib
import secrets
import smtplib
from datetime import datetime, timezone
from decimal import Decimal
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException, Response

from config import settings
from db.connections import get_farmers_connection
from logging_config import configure_logging
from security_crypto import decrypt_text, sign_auth_token, verify_auth_token

AUTH_COOKIE_NAME = "cropconnect_auth"
CSRF_COOKIE_NAME = "cropconnect_csrf"
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7
logger = configure_logging()


def decimal_to_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


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
        "landSize": decimal_to_float(row.get("land_size")),
        "sensorDeviceId": row.get("sensor_device_id") or "",
        "sensors": row.get("sensors") or "0",
        "pumps": row.get("pumps") or "0",
        "sensorSetupComplete": bool(row.get("sensor_setup_complete")),
        "sensorSetupStatus": row.get("sensor_setup_status") or "pending",
    }


def owner_profile_context(owner_id: int) -> dict[str, Any]:
    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM `users` WHERE `id` = %s LIMIT 1", (owner_id,))
                row = cursor.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not load account profile") from exc

    return user_row_to_payload(row) if row else {}


def generate_sensor_device_id() -> str:
    return f"ccdev_{int(datetime.now(timezone.utc).timestamp())}_{secrets.token_hex(8)}"


def auth_token_for_user(user: dict[str, Any]) -> str:
    return sign_auth_token({"user_id": user["id"], "email": user["email"]})


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_password_reset_email(email: str, reset_url: str) -> bool:
    if not smtp_configured():
        return False
    message = EmailMessage()
    message["Subject"] = "Reset your CropConnect password"
    message["From"] = settings.smtp_user
    message["To"] = email
    message.set_content(
        "Use this link to reset your CropConnect password:\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
    return True


def insert_chat_record(
    user_id: int,
    email: str,
    message_type: str,
    text: str,
    related_to_plant_or_soil: bool | None,
    sensor_data: dict[str, Any] | None,
    location: str | None,
) -> None:
    import json

    from db.connections import get_connection

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_messages (
                      user_id, email, message_type, text, related_to_plant_or_soil, sensor_data, location
                    )
                    VALUES (%s, %s, %s, %s, %s, CAST(%s AS JSON), %s)
                    """,
                    (
                        user_id,
                        email,
                        message_type,
                        text,
                        None if related_to_plant_or_soil is None else 1 if related_to_plant_or_soil else 0,
                        json.dumps(sensor_data or {}, ensure_ascii=False),
                        location or "",
                    ),
                )
            conn.commit()
    except Exception as exc:
        logger.exception("insert_chat_record failed: %s", exc)
        return


def set_auth_cookie(response: Response, token: str) -> str:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    set_csrf_cookie(response, csrf_token)
    return csrf_token


def set_csrf_cookie(response: Response, csrf_token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


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
        user_id = int(payload.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    email = str(payload.get("email") or "").strip().lower()

    if user_id < 1 or not email:
        raise HTTPException(status_code=401, detail="Login token is missing account ownership")
    return user_id, email


def require_sensor_read_access(
    device_id: str,
    authorization: str | None,
    auth_cookie: str | None = None,
    x_api_key: str | None = None,
    api_key: str | None = None,
) -> None:
    from services.esp32_service import api_key_matches

    if api_key_matches(x_api_key, api_key, device_id):
        return

    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not owner_device_id or owner_device_id != device_id:
        raise HTTPException(status_code=403, detail="Sensor device does not belong to this account")
