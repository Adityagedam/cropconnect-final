import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sys
import time
import urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from db import migrations as db_migrations
from db.connections import configure_connections, get_connection, get_farmers_connection, get_server_connection
from db_utils import (
    add_column_if_missing,
    column_exists,
    drop_column_if_exists,
    index_exists,
    modify_column_best_effort,
    quote_identifier,
    table_exists,
)
from http_client import request_json
from logging_config import configure_logging
from models import (
    TRANSLATION_BATCH_LIMIT,
    TRANSLATION_TEXT_LIMIT,
    TRANSLATION_TOTAL_CHAR_LIMIT,
    AIOrchestrateIn,
    AuthLoginIn,
    AuthPasswordResetConfirmIn,
    AuthPasswordResetRequestIn,
    AuthProfileUpdateIn,
    AuthSignupIn,
    ChatIn,
    CropRecommendIn,
    DashboardSnapshotIn,
    EmailValidatedModel,
    EnquiryIn,
    MarketInsightIn,
    PumpStateSaveIn,
    PumpTimersSaveIn,
    RelayStatusIn,
    TelemetryIn,
    TranslateIn,
    validate_email_text,
)
from pump_control import PumpStateIn, relay_command_text
from routers import ai as ai_router
from routers import auth as auth_router
from routers import farm as farm_router
from routers import market as market_router
from routers import public as public_router
from routers import pumps as pumps_router
from routers import sensors as sensors_router
from routers import weather as weather_router
from security_crypto import (
    decrypt_text,
    encrypt_text,
    hash_password,
    require_data_secret,
    verify_password,
)
from services import auth as auth_service

CORE_EXPORTS = (
    mysql,
    add_column_if_missing,
    column_exists,
    drop_column_if_exists,
    index_exists,
    modify_column_best_effort,
    quote_identifier,
    table_exists,
    get_server_connection,
    hash_password,
    verify_password,
    PumpStateIn,
    relay_command_text,
    re,
)

MODEL_EXPORTS = (
    AIOrchestrateIn,
    AuthLoginIn,
    AuthPasswordResetConfirmIn,
    AuthPasswordResetRequestIn,
    AuthProfileUpdateIn,
    AuthSignupIn,
    ChatIn,
    CropRecommendIn,
    DashboardSnapshotIn,
    EmailValidatedModel,
    EnquiryIn,
    MarketInsightIn,
    PumpStateSaveIn,
    PumpTimersSaveIn,
    RelayStatusIn,
    TelemetryIn,
    TranslateIn,
    TRANSLATION_BATCH_LIMIT,
    TRANSLATION_TEXT_LIMIT,
    TRANSLATION_TOTAL_CHAR_LIMIT,
    validate_email_text,
)

load_dotenv()
require_data_secret()
logger = configure_logging()


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


db_url = os.getenv("MYSQL_PUBLIC_URL")

if db_url:
    url = urlparse(db_url)
    DB_CONFIG = {
        "host": url.hostname,
        "port": int(url.port or 3306),
        "user": url.username,
        "password": url.password,
        "database": url.path[1:] or "railway"
    }
else:
    DB_CONFIG = {
        "host": env("MYSQL_HOST", "127.0.0.1"),
        "port": int(env("MYSQL_PORT", "3306")),
        "user": env("MYSQL_USER", "root"),
        "password": env("MYSQL_PASSWORD", ""),
        "database": env("MYSQL_DATABASE", "cropconnect"),
    }
FARMERS_DATABASE = env("MYSQL_FARMERS_DATABASE", "farmers")

API_KEY = os.getenv("ESP32_API_KEY", "")
ALLOW_GLOBAL_ESP32_API_KEY = env("ALLOW_GLOBAL_ESP32_API_KEY", "false").lower() in {"1", "true", "yes", "on"}
CONTACT_TO_EMAIL = env("CONTACT_TO_EMAIL", "cropconnectco@gmail.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "").strip()
DATA_GOV_MARKET_RESOURCE_URL = env(
    "DATA_GOV_MARKET_RESOURCE_URL",
    "https://api.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi",
).strip()
MARKET_PRICE_LIMIT = max(1, min(1000, int(env("MARKET_PRICE_LIMIT", "100"))))
FARM_TIMER_TIMEZONE = timezone(timedelta(minutes=int(env("FARM_TIMER_UTC_OFFSET_MINUTES", "330"))))
MYSQL_POOL_SIZE = max(1, int(env("MYSQL_POOL_SIZE", "5")))
configure_connections(DB_CONFIG, FARMERS_DATABASE, MYSQL_POOL_SIZE)
PUBLIC_LANDING_SENSOR_DEVICE_ID = env("PUBLIC_LANDING_SENSOR_DEVICE_ID", "").strip()
PUBLIC_TRANSLATION_ENABLED = env("PUBLIC_TRANSLATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
QUERY_API_KEY_ENABLED = env("QUERY_API_KEY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
ESP32_GET_WRITE_ENABLED = env("ESP32_GET_WRITE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
PASSWORD_RESET_TOKEN_TTL_MINUTES = int(env("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))
FRONTEND_PUBLIC_URL = env("FRONTEND_PUBLIC_URL", "https://cropconnect01.vercel.app").rstrip("/")
AUTH_COOKIE_NAME = "cropconnect_auth"
CSRF_COOKIE_NAME = "cropconnect_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
AUTH_COOKIE_SECURE = env("AUTH_COOKIE_SECURE", "true").lower() in {"1", "true", "yes", "on"}
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", "none").lower()
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7
TRANSLATION_CACHE_MAX_ITEMS = max(100, int(env("TRANSLATION_CACHE_MAX_ITEMS", "1000")))
TRANSLATION_CACHE: OrderedDict[str, str] = OrderedDict()
PUBLIC_RATE_LIMITS: dict[str, list[float]] = {}
PUBLIC_RATE_TABLE_READY = False
PUBLIC_RATE_LIMIT_DB_FAIL_OPEN = env("PUBLIC_RATE_LIMIT_DB_FAIL_OPEN", "false").lower() in {"1", "true", "yes", "on"}
TRUST_PROXY_HEADERS = env("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}
ENCRYPTED_PROFILE_FIELDS = {"name", "phone", "state", "location", "city", "village", "district"}
USER_TABLE = "users"
LEGACY_USER_TABLE = "sign-in"
DEFAULT_FRONTEND_ORIGINS = FRONTEND_PUBLIC_URL
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in env("FRONTEND_ORIGINS", DEFAULT_FRONTEND_ORIGINS).split(",")
    if origin.strip()
]
if "*" in FRONTEND_ORIGINS:
    raise RuntimeError("FRONTEND_ORIGINS cannot contain '*' when credentialed auth cookies are enabled")


def log_backend_error(context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)


def raise_public_error(status_code: int, detail: str, context: str, exc: Exception) -> None:
    log_backend_error(context, exc)
    raise HTTPException(status_code=status_code, detail=detail) from exc

PLANT_SOIL_TERMS = {
    "agriculture",
    "agronomy",
    "crop",
    "crops",
    "farm",
    "farming",
    "field",
    "plant",
    "plants",
    "seed",
    "seedling",
    "germination",
    "leaf",
    "leaves",
    "root",
    "roots",
    "stem",
    "flower",
    "fruit",
    "vegetable",
    "grain",
    "wheat",
    "rice",
    "maize",
    "corn",
    "soybean",
    "onion",
    "cotton",
    "sugarcane",
    "turmeric",
    "chilli",
    "groundnut",
    "soil",
    "moisture",
    "ph",
    "npk",
    "nitrogen",
    "phosphorus",
    "potassium",
    "fertilizer",
    "fertiliser",
    "compost",
    "manure",
    "irrigation",
    "irrigate",
    "water",
    "watering",
    "drip",
    "pest",
    "disease",
    "fungus",
    "fungal",
    "weed",
    "harvest",
    "sowing",
    "spray",
    "pesticide",
    "weather",
    "rain",
    "humidity",
    "temperature",
    "sensor",
    "sensors",
    "pani",
    "paani",
    "sinchai",
    "kheti",
    "khet",
    "mitti",
    "mati",
    "fasal",
    "khad",
    "khaad",
    "mausam",
    "barish",
    "baarish",
    "mandi",
    "bhav",
    "bazar",
}

MARKET_QUESTION_TERMS = {
    "market",
    "mandi",
    "price",
    "prices",
    "rate",
    "rates",
    "sell",
    "selling",
    "buyer",
    "buyers",
    "msp",
    "bhav",
    "bazar",
    "bazaar",
    "commodity",
}

MULTILINGUAL_PLANT_SOIL_TERMS = {
    "????", "???", "??????", "?????", "??", "????????", "???????",
}

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "te": "Telugu",
    "ta": "Tamil",
    "bn": "Bengali",
    "kn": "Kannada",
}

app = FastAPI(title="CropConnect ESP32 Ingestion API", version="1.0.0")

CSRF_EXEMPT_PATHS = {
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/password-reset-request",
    "/api/auth/password-reset-confirm",
    "/api/enquiries",
    "/api/utils/translate",
    "/api/telemetry/ingest",
    "/data",
}


@app.middleware("http")
async def reject_untrusted_browser_origins(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = (request.headers.get("origin") or "").rstrip("/")
        if origin and origin not in FRONTEND_ORIGINS:
            return PlainTextResponse("Origin is not allowed", status_code=403)
        auth_cookie = request.cookies.get(AUTH_COOKIE_NAME)
        if auth_cookie and request.url.path not in CSRF_EXEMPT_PATHS:
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
                return PlainTextResponse("CSRF token is missing or invalid", status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
)


def generate_esp32_api_key() -> str:
    return f"cc_esp32_{secrets.token_urlsafe(32)}"


def esp32_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def active_esp32_device_key(device_id: str, create_if_missing: bool = False) -> str:
    device = str(device_id or "").strip()
    if not device:
        return ""

    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT encrypted_key
                    FROM esp32_device_keys
                    WHERE device_id = %s AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (device,),
                )
                row = cursor.fetchone()
                if row:
                    return decrypt_text(row["encrypted_key"]) or ""
                if not create_if_missing:
                    return ""

                api_key = generate_esp32_api_key()
                cursor.execute(
                    """
                    INSERT INTO esp32_device_keys (device_id, key_hash, encrypted_key, status)
                    VALUES (%s, %s, %s, 'active')
                    """,
                    (device, esp32_key_hash(api_key), encrypt_text(api_key)),
                )
            conn.commit()
            return api_key
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(503, "Could not load ESP32 device key", "ESP32 device key lookup failed", exc)


def esp32_device_key_summary(device_id: str) -> dict[str, Any]:
    device = str(device_id or "").strip()
    if not device:
        return {"has_active_key": False}

    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, created_at, last_used_at
                    FROM esp32_device_keys
                    WHERE device_id = %s AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (device,),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not load ESP32 device key metadata", "ESP32 device key metadata lookup failed", exc)

    if not row:
        return {"has_active_key": False}
    return {
        "has_active_key": True,
        "created_at": decimal_to_float(row.get("created_at")),
        "last_used_at": decimal_to_float(row.get("last_used_at")),
    }


def rotate_esp32_device_key(device_id: str) -> str:
    device = str(device_id or "").strip()
    if not device:
        return ""

    api_key = generate_esp32_api_key()
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE esp32_device_keys
                    SET status = 'revoked', revoked_at = UTC_TIMESTAMP(), rotated_at = UTC_TIMESTAMP()
                    WHERE device_id = %s AND status = 'active'
                    """,
                    (device,),
                )
                cursor.execute(
                    """
                    INSERT INTO esp32_device_keys (device_id, key_hash, encrypted_key, status)
                    VALUES (%s, %s, %s, 'active')
                    """,
                    (device, esp32_key_hash(api_key), encrypt_text(api_key)),
                )
            conn.commit()
            return api_key
    except Exception as exc:
        raise_public_error(503, "Could not rotate ESP32 device key", "ESP32 device key rotation failed", exc)


def stored_esp32_key_matches(supplied_key: str, device_id: str) -> bool:
    device = str(device_id or "").strip()
    if not supplied_key or not device:
        return False

    supplied_hash = esp32_key_hash(supplied_key)
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """
                    SELECT id, key_hash
                    FROM esp32_device_keys
                    WHERE device_id = %s AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 5
                    """,
                    (device,),
                )
                rows = cursor.fetchall() or []
                matched_id = None
                for row in rows:
                    if hmac.compare_digest(str(row.get("key_hash") or ""), supplied_hash):
                        matched_id = row["id"]
                        break
                if matched_id is not None:
                    cursor.execute(
                        "UPDATE esp32_device_keys SET last_used_at = UTC_TIMESTAMP() WHERE id = %s",
                        (matched_id,),
                    )
                    conn.commit()
                    return True
        return False
    except Exception as exc:
        raise_public_error(503, "Could not validate ESP32 device key", "ESP32 device key validation failed", exc)


def supplied_esp32_key(x_api_key: str | None, api_key: str | None = None) -> str:
    return str(x_api_key or api_key or "").strip()


def require_esp32_get_write_enabled() -> None:
    if not ESP32_GET_WRITE_ENABLED:
        raise HTTPException(status_code=405, detail="ESP32 GET write endpoints are disabled; use POST")


def check_api_key(x_api_key: str | None, api_key: str | None = None, device_id: str | None = None) -> None:
    if api_key and not QUERY_API_KEY_ENABLED:
        raise HTTPException(status_code=401, detail="Query-string ESP32 API keys are disabled")
    supplied_key = supplied_esp32_key(x_api_key, api_key)
    if not supplied_key:
        raise HTTPException(status_code=401, detail="ESP32 API key is required")

    device = str(device_id or "").strip()
    if device:
        if stored_esp32_key_matches(supplied_key, device):
            return
        if ALLOW_GLOBAL_ESP32_API_KEY and API_KEY and hmac.compare_digest(supplied_key, API_KEY):
            return
        raise HTTPException(status_code=401, detail="Invalid ESP32 API key for this device")

    if not API_KEY:
        raise HTTPException(status_code=503, detail="ESP32_API_KEY is not configured")
    if not hmac.compare_digest(supplied_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid ESP32 API key")


def api_key_matches(x_api_key: str | None = None, api_key: str | None = None, device_id: str | None = None) -> bool:
    supplied_key = supplied_esp32_key(x_api_key, api_key)
    if not supplied_key:
        return False
    device = str(device_id or "").strip()
    if device:
        db_key_ok = stored_esp32_key_matches(supplied_key, device)
        return bool(
            db_key_ok
            or (ALLOW_GLOBAL_ESP32_API_KEY and API_KEY and hmac.compare_digest(supplied_key, API_KEY))
        )
    return bool(API_KEY and hmac.compare_digest(supplied_key, API_KEY))


def public_client_host(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if TRUST_PROXY_HEADERS and forwarded_for:
        return forwarded_for[:255]
    return (request.client.host if request.client else "unknown")[:255]


def run_database_migrations() -> None:
    db_migrations.run_database_migrations(sys.modules[__name__])


def rate_limit_public_request(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    rate_limit_named_key(bucket, public_client_host(request), limit, window_seconds)


def rate_limit_authenticated_request(owner_id: int, bucket: str, limit: int, window_seconds: int) -> None:
    rate_limit_named_key(bucket, f"user:{owner_id}", limit, window_seconds)


def rate_limit_named_key(bucket: str, client_key: str, limit: int, window_seconds: int) -> None:
    client_host = str(client_key or "unknown")[:255]
    try:
        with get_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "DELETE FROM public_rate_limits WHERE requested_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND)",
                    (window_seconds,),
                )
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM public_rate_limits
                    WHERE bucket = %s
                      AND client_host = %s
                      AND requested_at >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND)
                    """,
                    (bucket, client_host, window_seconds),
                )
                row = cursor.fetchone() or {}
                if int(row.get("count") or 0) >= limit:
                    raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
                cursor.execute(
                    "INSERT INTO public_rate_limits (bucket, client_host) VALUES (%s, %s)",
                    (bucket, client_host),
                )
            conn.commit()
        return
    except HTTPException:
        raise
    except Exception as exc:
        if not PUBLIC_RATE_LIMIT_DB_FAIL_OPEN:
            raise_public_error(503, "Rate limiter is unavailable", "Public rate limiter failed", exc)
        log_backend_error("MySQL rate limiter unavailable, using in-memory fallback", exc)

    key = f"{bucket}:{client_host}"
    now = time.time()
    recent = [
        timestamp
        for timestamp in PUBLIC_RATE_LIMITS.get(key, [])
        if now - timestamp < window_seconds
    ]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    recent.append(now)
    PUBLIC_RATE_LIMITS[key] = recent


def decimal_to_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def json_text(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def generate_sensor_device_id() -> str:
    return f"ccdev_{int(time.time())}_{secrets.token_hex(8)}"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_json_column(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def insert_chat_record(
    user_id: int | None,
    email: str | None,
    message_type: str,
    text: str,
    related_to_plant_or_soil: bool | None,
    sensor_data: dict[str, Any] | None,
    location: str | None,
) -> None:
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
                        email.strip().lower() if email else None,
                        message_type,
                        text,
                        None if related_to_plant_or_soil is None else (1 if related_to_plant_or_soil else 0),
                        json_text(sensor_data),
                        location or "",
                    ),
                )
            conn.commit()
    except Exception as exc:
        # Chat should still answer even if persistence is temporarily unavailable.
        logger.exception("Chat persistence failed: %s", exc)


def parse_ai_json(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start_candidates = [index for index in (cleaned.find("{"), cleaned.find("[")) if index != -1]
    if start_candidates:
        cleaned = cleaned[min(start_candidates):]
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end != -1:
        cleaned = cleaned[: end + 1]
    return json.loads(cleaned)


def require_openai() -> None:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for AI-powered decisions")


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def send_enquiry_email(payload: EnquiryIn) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_port = int(env("SMTP_PORT", "587"))

    if not smtp_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = f"CropConnect Enquiry from {payload.name}"
    msg["From"] = smtp_user
    msg["To"] = CONTACT_TO_EMAIL
    msg["Reply-To"] = payload.email
    msg.set_content(
        "\n".join(
            [
                f"Name: {payload.name}",
                f"Email: {payload.email}",
                f"Phone: {payload.phone or '-'}",
                f"Organization/Farm: {payload.organization or '-'}",
                "",
                "Message:",
                payload.message,
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

    return True


def send_password_reset_email(email: str, reset_url: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_port = int(env("SMTP_PORT", "587"))

    if not smtp_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = "Reset your CropConnect password"
    msg["From"] = smtp_user
    msg["To"] = email
    msg["Reply-To"] = CONTACT_TO_EMAIL
    msg.set_content(
        "\n".join(
            [
                "We received a request to reset your CropConnect password.",
                "",
                f"Reset link: {reset_url}",
                "",
                f"This link expires in {PASSWORD_RESET_TOKEN_TTL_MINUTES} minutes.",
                "If you did not request this, you can ignore this email.",
                "",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

    return True


def google_search(query: str, location: str | None = "") -> list[dict[str, str]]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []

    search_query = f"{query} {location or ''} agriculture farming India".strip()
    url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode(
        {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": search_query,
            "num": 5,
        }
    )
    try:
        data = request_json(url)
    except Exception:
        return []

    return [
        {
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "link": item.get("link", ""),
        }
        for item in data.get("items", [])
    ]


def is_plant_or_soil_question(message: str) -> bool:
    normalized = message.lower()
    normalized = normalized.replace("-", " ")
    words = {word.strip(".,?!:;()[]{}\"'") for word in normalized.split()}

    if words & PLANT_SOIL_TERMS:
        return True

    if any(term in normalized for term in PLANT_SOIL_TERMS if len(term) > 4):
        return True

    return any(term in normalized for term in MULTILINGUAL_PLANT_SOIL_TERMS)


def is_market_question(message: str) -> bool:
    normalized = message.lower().replace("-", " ")
    words = {word.strip(".,?!:;()[]{}\"'") for word in normalized.split()}
    return bool(words & MARKET_QUESTION_TERMS) or any(term in normalized for term in MARKET_QUESTION_TERMS if len(term) > 4)


def selected_language(payload: ChatIn) -> str:
    code = (payload.language or "en").lower().split("-", 1)[0]
    return code if code in LANGUAGE_NAMES else "en"


def selected_language_name(language: str | None) -> str:
    code = (language or "en").lower().split("-", 1)[0]
    return LANGUAGE_NAMES.get(code, LANGUAGE_NAMES["en"])


def classify_farm_scope_with_ai(message: str, language: str = "en") -> bool:
    if not OPENAI_API_KEY:
        return is_plant_or_soil_question(message)

    prompt = (
        "Classify whether the latest user message is asking for help about agriculture, farming, crops, soil, "
        "irrigation, farm sensors, pumps, farm weather, pests, fertilizer, or mandi/market decisions. "
        "Return {\"in_scope\":true} only when the actual request is about those farm topics. "
        "Return {\"in_scope\":false} for general knowledge, coding, entertainment, politics, adult content, "
        "medical/legal/financial advice not tied to farming, or messages that merely mention a farm word as a trick. "
        "Return strict JSON only."
    )
    data = request_json(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"message": message, "selected_language": language},
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 40,
        },
        {"Authorization": f"Bearer {OPENAI_API_KEY}"},
    )
    raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = parse_ai_json(raw)
    if not isinstance(parsed, dict) or "in_scope" not in parsed:
        raise ValueError("Scope classifier returned an unexpected response")
    return bool(parsed.get("in_scope"))


def translate_texts_with_ai(texts: list[str], target_lang: str) -> list[str]:
    target = target_lang.lower().strip()
    if target in ("en", "english"):
        return texts

    def cache_key(text: str) -> str:
        return f"{target}:{text}"

    def cached_value(text: str) -> str | None:
        key = cache_key(text)
        if key not in TRANSLATION_CACHE:
            return None
        TRANSLATION_CACHE.move_to_end(key)
        return TRANSLATION_CACHE[key]

    def remember_translation(source: str, translated: str) -> None:
        key = cache_key(source)
        TRANSLATION_CACHE[key] = translated
        TRANSLATION_CACHE.move_to_end(key)
        while len(TRANSLATION_CACHE) > TRANSLATION_CACHE_MAX_ITEMS:
            TRANSLATION_CACHE.popitem(last=False)

    missing = [text for text in texts if text and cached_value(text) is None]

    if missing:
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        prompt = (
            "Translate this JSON array of CropConnect farming website UI strings from English "
            f"to {target_lang}. Preserve placeholders like {{name}}, {{moisture}}, {{temp}}, HTML tags, "
            "numbers, punctuation, and product names. Return only a JSON array of translated strings "
            "in the same order, with no explanation.\n\n"
            + json.dumps(missing, ensure_ascii=False)
        )

        try:
            response = request_json(
                "https://api.openai.com/v1/chat/completions",
                payload={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a precise UI localization engine. Output valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                },
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            )
            raw = response["choices"][0]["message"]["content"].strip()
            translated_items = json.loads(raw)
            if not isinstance(translated_items, list) or len(translated_items) != len(missing):
                raise ValueError("Translator returned an unexpected response shape")

            for source, translated in zip(missing, translated_items, strict=False):
                remember_translation(source, str(translated))
        except HTTPException:
            raise
        except Exception as exc:
            raise_public_error(502, "Translation failed", "Translation request failed", exc)

    return [cached_value(text) or text for text in texts]


def owner_profile_context(owner_id: int) -> dict[str, Any]:
    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM `users` WHERE `id` = %s LIMIT 1", (owner_id,))
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not load account profile", "Owner profile lookup failed", exc)

    return user_row_to_payload(row) if row else {}


weather_code_condition = weather_router.weather_code_condition
market_text = market_router.market_text
market_number = market_router.market_number
market_record_value = market_router.market_record_value
normalize_market_record = market_router.normalize_market_record
market_record_has_price = market_router.market_record_has_price
market_payload_from_records = market_router.market_payload_from_records
data_gov_market_records = market_router.data_gov_market_records
user_market_location = market_router.user_market_location
live_market_context_for_profile = market_router.live_market_context_for_profile
build_market_insight_messages = market_router.build_market_insight_messages
normalize_market_insight_payload = market_router.normalize_market_insight_payload
user_row_to_payload = auth_service.user_row_to_payload
set_auth_cookie = auth_service.set_auth_cookie
set_csrf_cookie = auth_service.set_csrf_cookie
clear_auth_cookie = auth_service.clear_auth_cookie
auth_token_from_request = auth_service.auth_token_from_request
require_auth_owner = auth_service.require_auth_owner
require_sensor_read_access = auth_service.require_sensor_read_access
auth_token_for_user = auth_service.auth_token_for_user
reading_to_sensor_list = sensors_router.reading_to_sensor_list
latest_sensor_context = sensors_router.latest_sensor_context
insert_telemetry_reading = sensors_router.insert_telemetry_reading
first_present = sensors_router.first_present
esp32_payload_to_telemetry = sensors_router.esp32_payload_to_telemetry
pump_id_to_relay_number = pumps_router.pump_id_to_relay_number
parse_timer_start_minutes = pumps_router.parse_timer_start_minutes
format_timer_start_time = pumps_router.format_timer_start_time
timer_row_is_active = pumps_router.timer_row_is_active
active_timer_pump_ids_from_db = pumps_router.active_timer_pump_ids_from_db
latest_relay_command_states_from_db = pumps_router.latest_relay_command_states_from_db
sync_relay_commands_from_db = pumps_router.sync_relay_commands_from_db
save_relay_applied_states_to_db = pumps_router.save_relay_applied_states_to_db
latest_relay_applied_status_from_db = pumps_router.latest_relay_applied_status_from_db
relay_status_payload_from_db = pumps_router.relay_status_payload_from_db
health = public_router.health
root = public_router.root


def register_routers() -> None:
    core = sys.modules[__name__]
    auth_service._bind_core(core)
    market_router._bind_core(core)
    weather_router._bind_core(core)
    app.include_router(public_router.create_router(core))
    app.include_router(auth_router.create_router(core))
    app.include_router(sensors_router.create_router(core))
    app.include_router(pumps_router.create_router(core))
    app.include_router(farm_router.create_router(core))
    app.include_router(market_router.create_router(core))
    app.include_router(weather_router.create_router(core))
    app.include_router(ai_router.create_router(core))


register_routers()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=env("HOST", "0.0.0.0"), port=int(env("PORT", "8001")))
