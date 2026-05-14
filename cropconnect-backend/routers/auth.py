# Authentication and profile API routes.
import hashlib
import secrets
import urllib.parse
from typing import Any

import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from config import settings
from db.connections import get_connection, get_farmers_connection
from logging_config import configure_logging
from models import AuthLoginIn, AuthPasswordResetConfirmIn, AuthPasswordResetRequestIn, AuthProfileUpdateIn, AuthSignupIn
from security_crypto import encrypt_text, hash_password, refresh_auth_token, verify_password
from services import rate_limit as rate_limit_service
from services.auth_service import (
    auth_token_for_user,
    auth_token_from_request,
    clear_auth_cookie,
    generate_sensor_device_id,
    send_password_reset_email,
    set_auth_cookie,
    set_csrf_cookie,
    smtp_configured,
    token_hash,
    user_row_to_payload,
)
from services.deps import get_current_user

router = APIRouter()
logger = configure_logging()

ENCRYPTED_PROFILE_FIELDS = {"name", "phone", "state", "location", "city", "village", "district"}


def raise_public_error(status_code: int, detail: str, _context: str, exc: Exception) -> None:
    raise HTTPException(status_code=status_code, detail=detail) from exc


def load_owner_profile(owner_id: int) -> dict[str, Any]:
    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM `users` WHERE `id` = %s LIMIT 1", (owner_id,))
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not load account profile", "Owner profile lookup failed", exc)
    return user_row_to_payload(row) if row else {}


def rate_limit_public_request(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    original_get_connection = rate_limit_service.get_connection
    rate_limit_service.get_connection = get_connection
    try:
        rate_limit_service.rate_limit_public_request(request, bucket, limit, window_seconds)
    finally:
        rate_limit_service.get_connection = original_get_connection


@router.post("/api/auth/signup")
def auth_signup(payload: AuthSignupIn, request: Request, response: Response):
    email = payload.email.strip().lower()
    email_bucket = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    rate_limit_public_request(request, "auth-signup-ip", limit=5, window_seconds=60 * 60)
    rate_limit_public_request(request, f"auth-signup-email-{email_bucket}", limit=3, window_seconds=60 * 60)

    insert_sql = """
        INSERT INTO `users` (
          `email`,
          `password`,
          `phone`,
          `name`,
          `state`,
          `location`,
          `land_size`,
          `location_type`,
          `district`,
          `city`,
          `village`,
          `sensor_device_id`,
          `sensors`,
          `pumps`,
          `sensor_setup_complete`,
          `sensor_setup_status`
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    location_type = payload.location_type or "city"
    city = payload.city or (payload.location if location_type == "city" else "")
    village = payload.village or (payload.location if location_type == "village" else "")
    sensor_device_id = generate_sensor_device_id()
    values = (
        email,
        hash_password(payload.password),
        encrypt_text(payload.phone or ""),
        encrypt_text(payload.name),
        encrypt_text(payload.state or ""),
        encrypt_text(payload.location or ""),
        payload.land_size,
        location_type,
        encrypt_text(payload.district or ""),
        encrypt_text(city or ""),
        encrypt_text(village or ""),
        sensor_device_id,
        payload.sensors or "0",
        payload.pumps or "0",
        1 if payload.sensor_setup_complete else 0,
        payload.sensor_setup_status or "pending",
    )

    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(insert_sql, values)
                user_id = cursor.lastrowid
                cursor.execute("SELECT * FROM `users` WHERE `id` = %s", (user_id,))
                row = cursor.fetchone()
            conn.commit()
    except mysql.connector.IntegrityError as exc:
        message = str(exc).lower()
        if "sensor_device_id" in message:
            raise HTTPException(status_code=409, detail="Could not assign a unique sensor device. Please try again.") from exc
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    except Exception as exc:
        raise_public_error(503, "Could not create account", "Signup failed", exc)

    user = user_row_to_payload(row)
    token = auth_token_for_user(user)
    csrf_token = set_auth_cookie(response, token)
    return {
        "ok": True,
        "user": user,
        "token": token,
        "csrfToken": csrf_token,
    }


@router.post("/api/auth/login")
def auth_login(payload: AuthLoginIn, request: Request, response: Response):
    email = payload.email.strip().lower()
    email_bucket = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    rate_limit_public_request(request, "auth-login-ip", limit=20, window_seconds=15 * 60)
    rate_limit_public_request(request, f"auth-login-email-{email_bucket}", limit=8, window_seconds=15 * 60)

    query = """
        SELECT
          *
        FROM `users`
        WHERE `email` = %s
        LIMIT 1
    """

    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, (email,))
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not check login", "Login check failed", exc)

    if not row or not verify_password(payload.password, row.get("password", "")):
        raise HTTPException(status_code=401, detail="Email and password do not match")

    user = user_row_to_payload(row)
    token = auth_token_for_user(user)
    csrf_token = set_auth_cookie(response, token)
    return {
        "ok": True,
        "user": user,
        "token": token,
        "csrfToken": csrf_token,
    }


@router.post("/api/auth/logout")
def auth_logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/api/auth/csrf")
def auth_csrf(response: Response, _current_user: tuple[int, str] = Depends(get_current_user)):
    csrf_token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, csrf_token)
    return {"ok": True, "csrfToken": csrf_token}


@router.get("/api/auth/refresh")
def auth_refresh(response: Response, request: Request):
    token = auth_token_from_request(request.headers.get("authorization"), request.cookies.get("cropconnect_auth"))
    fresh_token = refresh_auth_token(token)
    if not fresh_token:
        return {"ok": True, "refreshed": False}
    csrf_token = set_auth_cookie(response, fresh_token)
    return {"ok": True, "refreshed": True, "token": fresh_token, "csrfToken": csrf_token}


@router.get("/api/auth/profile")
def auth_profile(current_user: tuple[int, str] = Depends(get_current_user)):
    owner_id, _owner_email = current_user
    user = load_owner_profile(owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": user}


@router.post("/api/auth/password-reset-request")
def auth_password_reset_request(payload: AuthPasswordResetRequestIn, request: Request):
    email = payload.email.strip().lower()
    email_bucket = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    rate_limit_public_request(request, "password-reset", limit=3, window_seconds=15 * 60)
    rate_limit_public_request(request, f"password-reset-email-{email_bucket}", limit=3, window_seconds=60 * 60)

    if smtp_configured():
        try:
            with get_farmers_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT id FROM `users` WHERE `email` = %s LIMIT 1", (email,))
                    row = cursor.fetchone()
                    if row:
                        reset_token = secrets.token_urlsafe(32)
                        reset_url = (
                            f"{settings.frontend_public_url.rstrip('/')}/reset-password?"
                            + urllib.parse.urlencode({"email": email, "token": reset_token})
                        )
                        cursor.execute(
                            """
                            INSERT INTO password_reset_tokens (email, token_hash, expires_at)
                            VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE))
                            """,
                            (email, token_hash(reset_token), settings.password_reset_token_ttl_minutes),
                        )
                        conn.commit()
                        try:
                            send_password_reset_email(email, reset_url)
                        except Exception as smtp_exc:
                            logger.exception("Password reset email failed for %s: %s", email, smtp_exc)
                    conn.commit()
        except Exception as exc:
            logger.exception("Password reset request failed for %s: %s", email, exc)

    return {
        "ok": True,
        "message": "If an account exists, password reset instructions will be sent.",
    }


@router.post("/api/auth/password-reset-confirm")
def auth_password_reset_confirm(payload: AuthPasswordResetConfirmIn, request: Request):
    email = payload.email.strip().lower()
    email_bucket = hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]
    rate_limit_public_request(request, "password-reset-confirm", limit=8, window_seconds=15 * 60)
    rate_limit_public_request(request, f"password-confirm-email-{email_bucket}", limit=5, window_seconds=60 * 60)
    hashed_token = token_hash(payload.token.strip())

    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM password_reset_tokens
                    WHERE email = %s
                      AND token_hash = %s
                      AND used_at IS NULL
                      AND expires_at > UTC_TIMESTAMP()
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (email, hashed_token),
                )
                reset_row = cursor.fetchone()
                if not reset_row:
                    raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

                cursor.execute(
                    "UPDATE `users` SET `password` = %s WHERE `email` = %s",
                    (hash_password(payload.password), email),
                )
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
                cursor.execute(
                    "UPDATE password_reset_tokens SET used_at = UTC_TIMESTAMP() WHERE id = %s",
                    (reset_row["id"],),
                )
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(503, "Could not reset password", "Password reset confirm failed", exc)

    return {"ok": True, "message": "Password has been reset"}


@router.post("/api/auth/profile")
def auth_profile_update(payload: AuthProfileUpdateIn, current_user: tuple[int, str] = Depends(get_current_user)):
    owner_id, _owner_email = current_user

    updates: list[str] = []
    values: list[Any] = []
    field_map = {
        "name": ("name", "`name` = %s"),
        "phone": ("phone", "`phone` = %s"),
        "state": ("state", "`state` = %s"),
        "location": ("location", "`location` = %s"),
        "land_size": ("land_size", "`land_size` = %s"),
        "location_type": ("location_type", "`location_type` = %s"),
        "district": ("district", "`district` = %s"),
        "city": ("city", "`city` = %s"),
        "village": ("village", "`village` = %s"),
        "sensors": ("sensors", "`sensors` = %s"),
        "pumps": ("pumps", "`pumps` = %s"),
        "sensor_setup_status": ("sensor_setup_status", "`sensor_setup_status` = %s"),
    }

    data = payload.model_dump(exclude_unset=True)
    if "sensor_device_id" in data and data["sensor_device_id"] is not None:
        requested_device_id = str(data["sensor_device_id"] or "").strip()
        try:
            with get_farmers_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT sensor_device_id FROM `users` WHERE `id` = %s", (owner_id,))
                    current_row = cursor.fetchone()
        except Exception as exc:
            raise_public_error(503, "Could not validate sensor device", "Sensor device validation failed", exc)
        current_device_id = str((current_row or {}).get("sensor_device_id") or "").strip()
        if current_device_id and requested_device_id and requested_device_id != current_device_id:
            raise HTTPException(
                status_code=403,
                detail="Sensor device is already assigned. Use a verified device-pairing flow before changing it.",
            )
        if not current_device_id:
            updates.append("`sensor_device_id` = %s")
            values.append(generate_sensor_device_id())

    for input_name, (column_name, assignment_sql) in field_map.items():
        if input_name in data and data[input_name] is not None:
            updates.append(assignment_sql)
            value = data[input_name]
            values.append(encrypt_text(value) if column_name in ENCRYPTED_PROFILE_FIELDS else value)

    if "sensor_setup_complete" in data and data["sensor_setup_complete"] is not None:
        updates.append("`sensor_setup_complete` = %s")
        values.append(1 if data["sensor_setup_complete"] else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No profile fields provided")

    values.append(owner_id)

    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("UPDATE `users` SET " + ", ".join(updates) + " WHERE `id` = %s", tuple(values))
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="User not found")
                cursor.execute(
                    "SELECT * FROM `users` WHERE `id` = %s",
                    (owner_id,),
                )
                row = cursor.fetchone()
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(503, "Could not update profile", "Profile update failed", exc)

    return {"ok": True, "user": user_row_to_payload(row)}
