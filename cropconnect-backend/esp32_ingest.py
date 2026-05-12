import os
import json
import hashlib
import hmac
import re
import secrets
import smtplib
import time
import threading
import urllib.parse
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any
from urllib.parse import urlparse
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from crop_ai_agent import build_crop_recommendation_messages, has_core_sensor_context, missing_crop_readings
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
from pump_control import (
    PumpStateIn,
    relay_command_text,
    update_relay_applied_state,
)
from security_crypto import (
    decrypt_text,
    encrypt_text,
    hash_password,
    require_data_secret,
    sign_auth_token,
    verify_auth_token,
    verify_password,
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
PUBLIC_LANDING_SENSOR_DEVICE_ID = env("PUBLIC_LANDING_SENSOR_DEVICE_ID", "").strip()
PUBLIC_TRANSLATION_ENABLED = env("PUBLIC_TRANSLATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
QUERY_API_KEY_ENABLED = env("QUERY_API_KEY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
ESP32_GET_WRITE_ENABLED = env("ESP32_GET_WRITE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
TRANSLATION_TEXT_LIMIT = 1000
TRANSLATION_BATCH_LIMIT = 40
TRANSLATION_TOTAL_CHAR_LIMIT = 12000
PASSWORD_RESET_TOKEN_TTL_MINUTES = int(env("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))
FRONTEND_PUBLIC_URL = env("FRONTEND_PUBLIC_URL", "https://cropconnect01.vercel.app").rstrip("/")
AUTH_COOKIE_NAME = "cropconnect_auth"
CSRF_COOKIE_NAME = "cropconnect_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
AUTH_COOKIE_SECURE = env("AUTH_COOKIE_SECURE", "true").lower() in {"1", "true", "yes", "on"}
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", "none").lower()
AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 7
TRANSLATION_CACHE: dict[str, dict[str, str]] = {}
PUBLIC_RATE_LIMITS: dict[str, list[float]] = {}
PUBLIC_RATE_TABLE_READY = False
PUBLIC_RATE_LIMIT_DB_FAIL_OPEN = env("PUBLIC_RATE_LIMIT_DB_FAIL_OPEN", "false").lower() in {"1", "true", "yes", "on"}
TRUST_PROXY_HEADERS = env("TRUST_PROXY_HEADERS", "false").lower() in {"1", "true", "yes", "on"}
ENCRYPTED_PROFILE_FIELDS = {"name", "phone", "state", "location", "city", "village", "district"}
USER_TABLE = "users"
LEGACY_USER_TABLE = "sign-in"
MAIN_DB_POOL = None
FARMERS_DB_POOLS: dict[str, pooling.MySQLConnectionPool] = {}
MAIN_DB_POOL_LOCK = threading.Lock()
FARMERS_DB_POOLS_LOCK = threading.Lock()
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
    "????", "???", "??????", "???", "????", "????", "??????", "??????", "???", "????", "???", "???",
    "????", "???", "????", "???", "????", "?????", "??", "??????", "????",
    "???", "????", "?????", "????", "????", "?????", "????????", "??????", "?????",
    "?????", "?????", "???", "????", "??????", "????", "??????", "????", "???",
    "???", "?????", "????", "???", "???", "???", "????????", "???", "??????",
    "????", "???", "?????", "????", "????", "???????", "??????", "??????", "???", "???",
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


def validate_email_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    _name, parsed_email = parseaddr(text)
    local_part, separator, domain = parsed_email.partition("@")
    if (
        parsed_email != text
        or not separator
        or not local_part
        or not domain
        or any(char.isspace() for char in parsed_email)
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or len(parsed_email) > 254
    ):
        raise ValueError("Enter a valid email address")
    return parsed_email


class EmailValidatedModel(BaseModel):
    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def validate_email_field(cls, value: Any) -> Any:
        if value is None or value == "":
            return value
        return validate_email_text(value)


class TelemetryIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    soil_moisture: float | None = Field(default=None, ge=0, le=100)
    humidity: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=-20, le=80)
    ph: float | None = Field(default=None, ge=0, le=14)
    nitrogen: float | None = Field(default=None, ge=0)
    phosphorus: float | None = Field(default=None, ge=0)
    potassium: float | None = Field(default=None, ge=0)


class EnquiryIn(EmailValidatedModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default="", max_length=40)
    organization: str | None = Field(default="", max_length=160)
    message: str = Field(min_length=1, max_length=4000)


class ChatIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    message: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="en", max_length=16)
    input_language: str = Field(default="en", max_length=16)
    device_id: str | None = Field(default="", max_length=80)
    sensor_data: dict[str, Any] = Field(default_factory=dict)
    market_data: dict[str, Any] = Field(default_factory=dict)
    weather_data: dict[str, Any] = Field(default_factory=dict)
    location: str | None = Field(default="", max_length=160)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


class AuthSignupIn(EmailValidatedModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    phone: str | None = Field(default="", max_length=30)
    state: str | None = Field(default="", max_length=120)
    location: str | None = Field(default="", max_length=255)
    land_size: float | None = Field(default=None, ge=0)
    location_type: str | None = Field(default="city", max_length=20)
    district: str | None = Field(default="", max_length=120)
    city: str | None = Field(default="", max_length=120)
    village: str | None = Field(default="", max_length=120)
    sensors: str | None = Field(default="0", max_length=20)
    pumps: str | None = Field(default="0", max_length=20)
    sensor_setup_complete: bool = False
    sensor_setup_status: str | None = Field(default="pending", max_length=40)


class AuthLoginIn(EmailValidatedModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class AuthPasswordResetRequestIn(EmailValidatedModel):
    email: str = Field(min_length=3, max_length=255)


class AuthPasswordResetConfirmIn(EmailValidatedModel):
    email: str = Field(min_length=3, max_length=255)
    token: str = Field(min_length=20, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class AuthProfileUpdateIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    state: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    land_size: float | None = Field(default=None, ge=0)
    location_type: str | None = Field(default=None, max_length=20)
    district: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    sensor_device_id: str | None = Field(default=None, max_length=80)
    sensors: str | None = Field(default=None, max_length=20)
    pumps: str | None = Field(default=None, max_length=20)
    sensor_setup_complete: bool | None = None
    sensor_setup_status: str | None = Field(default=None, max_length=40)


class PumpStateSaveIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    device_id: str | None = Field(default="", max_length=80)
    pump_id: str = Field(min_length=1, max_length=40)
    on: bool
    runtime: int | None = Field(default=0, ge=0)
    schedule: dict[str, Any] = Field(default_factory=dict)
    sent_to_esp32: bool = False
    message: str | None = Field(default="", max_length=255)


class RelayStatusIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    relays: dict[str, bool] = Field(default_factory=dict)


class PumpTimersSaveIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    timers: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class TranslateIn(BaseModel):
    text: str | None = Field(default=None, max_length=TRANSLATION_TEXT_LIMIT)
    texts: list[str] | None = Field(default=None, max_length=TRANSLATION_BATCH_LIMIT)
    target_lang: str = Field(min_length=2, max_length=40)

    @field_validator("texts")
    @classmethod
    def validate_text_items(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        total_characters = 0
        normalized_items: list[str] = []
        for item in value:
            text = str(item or "")
            if len(text) > TRANSLATION_TEXT_LIMIT:
                raise ValueError(f"Each translation item must be {TRANSLATION_TEXT_LIMIT} characters or fewer")
            total_characters += len(text)
            normalized_items.append(text)
        if total_characters > TRANSLATION_TOTAL_CHAR_LIMIT:
            raise ValueError(f"Translation batch must be {TRANSLATION_TOTAL_CHAR_LIMIT} characters or fewer")
        return normalized_items


class CropRecommendIn(BaseModel):
    goal: str = Field(default="balanced", max_length=40)
    season: str | None = Field(default="", max_length=80)
    language: str | None = Field(default="en", max_length=20)
    device_id: str | None = Field(default="", max_length=80)
    sensor_source: str | None = Field(default="", max_length=40)


class MarketInsightIn(BaseModel):
    language: str | None = Field(default="en", max_length=20)
    objective: str = Field(default="Give practical selling guidance from live local mandi records", max_length=300)


class AIOrchestrateIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default="", max_length=160)
    language: str | None = Field(default="en", max_length=20)
    sensor_data: dict[str, Any] = Field(default_factory=dict)
    pump_data: dict[str, Any] = Field(default_factory=dict)
    timers: dict[str, Any] = Field(default_factory=dict)
    weather_data: dict[str, Any] | None = Field(default=None)
    market_data: dict[str, Any] | None = Field(default=None)
    objective: str = Field(default="Optimize farm health and irrigation decisions", max_length=500)


class DashboardSnapshotIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    device_id: str | None = Field(default="", max_length=80)
    source: str | None = Field(default="dashboard", max_length=40)
    sensor_data: dict[str, Any] = Field(default_factory=dict)
    pump_data: dict[str, Any] = Field(default_factory=dict)
    timers: dict[str, Any] = Field(default_factory=dict)
    weather_data: dict[str, Any] | None = Field(default=None)
    market_data: dict[str, Any] | None = Field(default=None)
    telemetry_packet: dict[str, Any] = Field(default_factory=dict)


def get_connection():
    global MAIN_DB_POOL
    if MAIN_DB_POOL is None:
        with MAIN_DB_POOL_LOCK:
            if MAIN_DB_POOL is None:
                MAIN_DB_POOL = pooling.MySQLConnectionPool(
                    pool_name="cropconnect_main",
                    pool_size=MYSQL_POOL_SIZE,
                    pool_reset_session=True,
                    **DB_CONFIG,
                )
    return MAIN_DB_POOL.get_connection()


def get_server_connection():
    config = {**DB_CONFIG}
    config.pop("database", None)
    return mysql.connector.connect(**config)


def get_farmers_connection(database: str | None = FARMERS_DATABASE):
    pool_key = database or FARMERS_DATABASE
    if pool_key not in FARMERS_DB_POOLS:
        with FARMERS_DB_POOLS_LOCK:
            if pool_key not in FARMERS_DB_POOLS:
                FARMERS_DB_POOLS[pool_key] = pooling.MySQLConnectionPool(
                    pool_name=f"cropconnect_farmers_{hashlib.sha1(pool_key.encode('utf-8')).hexdigest()[:12]}",
                    pool_size=MYSQL_POOL_SIZE,
                    pool_reset_session=True,
                    **{**DB_CONFIG, "database": pool_key},
                )
    return FARMERS_DB_POOLS[pool_key].get_connection()


def migrate_legacy_device_api_keys(cursor, table_schema: str) -> None:
    if not column_exists(cursor, table_schema, "devices", "api_key"):
        return

    cursor.execute(
        """
        SELECT device_id, api_key
        FROM devices
        WHERE api_key IS NOT NULL AND TRIM(api_key) <> ''
        """
    )
    rows = cursor.fetchall() or []
    for row in rows:
        device_id = str((row.get("device_id") if isinstance(row, dict) else row[0]) or "").strip()
        legacy_key = str((row.get("api_key") if isinstance(row, dict) else row[1]) or "").strip()
        if not device_id or not legacy_key:
            continue

        key_hash = esp32_key_hash(legacy_key)
        cursor.execute("SELECT id FROM esp32_device_keys WHERE key_hash = %s LIMIT 1", (key_hash,))
        if cursor.fetchone():
            continue
        cursor.execute(
            "SELECT id FROM esp32_device_keys WHERE device_id = %s AND status = 'active' LIMIT 1",
            (device_id,),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO esp32_device_keys (device_id, key_hash, encrypted_key, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (device_id, key_hash, encrypt_text(legacy_key)),
        )


def ensure_sensor_tables() -> None:
    database = DB_CONFIG["database"]
    with get_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_readings (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL,
                  soil_moisture DECIMAL(6,2) NULL,
                  humidity DECIMAL(6,2) NULL,
                  temperature DECIMAL(6,2) NULL,
                  ph DECIMAL(5,2) NULL,
                  nitrogen DECIMAL(8,2) NULL,
                  phosphorus DECIMAL(8,2) NULL,
                  potassium DECIMAL(8,2) NULL,
                  raw_payload JSON NULL,
                  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_device_recorded_at (device_id, recorded_at),
                  INDEX idx_recorded_at (recorded_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL UNIQUE,
                  display_name VARCHAR(120) NULL,
                  location VARCHAR(160) NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS esp32_device_keys (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL,
                  key_hash CHAR(64) NOT NULL UNIQUE,
                  encrypted_key TEXT NOT NULL,
                  status VARCHAR(20) NOT NULL DEFAULT 'active',
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  last_used_at TIMESTAMP NULL,
                  rotated_at TIMESTAMP NULL,
                  revoked_at TIMESTAMP NULL,
                  PRIMARY KEY (id),
                  INDEX idx_device_key_status (device_id, status, created_at),
                  INDEX idx_device_key_hash_status (key_hash, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            migrate_legacy_device_api_keys(cursor, database)
            drop_column_if_exists(cursor, database, "devices", "api_key")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pump_states (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  device_id VARCHAR(80) NULL,
                  pump_id VARCHAR(40) NOT NULL,
                  is_on TINYINT(1) NOT NULL DEFAULT 0,
                  runtime_minutes INT UNSIGNED NOT NULL DEFAULT 0,
                  schedule JSON NULL,
                  sent_to_esp32 TINYINT(1) NOT NULL DEFAULT 0,
                  message VARCHAR(255) NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_pump_user_created (user_id, email, created_at),
                  INDEX idx_pump_device_created (device_id, pump_id, created_at),
                  INDEX idx_pump_id_created (pump_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            add_column_if_missing(cursor, database, "pump_states", "device_id", "VARCHAR(80) NULL")
            if not index_exists(cursor, database, "pump_states", "idx_pump_device_created"):
                cursor.execute("CREATE INDEX idx_pump_device_created ON pump_states (device_id, pump_id, created_at)")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS relay_statuses (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL,
                  relay_number TINYINT UNSIGNED NOT NULL,
                  is_on TINYINT(1) NOT NULL DEFAULT 0,
                  reported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_relay_device_number (device_id, relay_number),
                  INDEX idx_relay_device_reported (device_id, reported_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pump_timers (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  device_id VARCHAR(80) NULL,
                  pump_id VARCHAR(40) NOT NULL,
                  timer_key VARCHAR(80) NOT NULL,
                  start_time VARCHAR(10) NOT NULL,
                  duration_minutes INT UNSIGNED NOT NULL,
                  days JSON NULL,
                  active TINYINT(1) NOT NULL DEFAULT 1,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_timer_owner (`user_id`, `email`, `pump_id`, `timer_key`),
                  INDEX idx_timer_owner (user_id, email, pump_id),
                  INDEX idx_timer_device_active (device_id, active, pump_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            add_column_if_missing(cursor, database, "pump_timers", "device_id", "VARCHAR(80) NULL")
            if not index_exists(cursor, database, "pump_timers", "idx_timer_device_active"):
                cursor.execute("CREATE INDEX idx_timer_device_active ON pump_timers (device_id, active, pump_id)")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  message_type VARCHAR(20) NOT NULL,
                  text TEXT NOT NULL,
                  related_to_plant_or_soil TINYINT(1) NULL,
                  sensor_data JSON NULL,
                  location VARCHAR(160) NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_chat_owner_created (user_id, email, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_snapshots (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  device_id VARCHAR(80) NULL,
                  source VARCHAR(40) NULL,
                  sensor_data JSON NULL,
                  pump_data JSON NULL,
                  timers JSON NULL,
                  weather_data JSON NULL,
                  market_data JSON NULL,
                  telemetry_packet JSON NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_snapshot_owner_created (user_id, email, created_at),
                  INDEX idx_snapshot_device_created (device_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        conn.commit()


def ensure_farmers_tables() -> None:
    create_db_sql = """
        CREATE DATABASE IF NOT EXISTS {database}
          CHARACTER SET utf8mb4
          COLLATE utf8mb4_unicode_ci
    """.format(database=quote_identifier(FARMERS_DATABASE))
    create_user_sql = """
        CREATE TABLE IF NOT EXISTS `users` (
          `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          `email` VARCHAR(255) NOT NULL,
          `password` VARCHAR(255) NOT NULL,
          `phone` VARCHAR(30) NULL,
          `name` VARCHAR(120) NULL,
          `state` VARCHAR(120) NULL,
          `location` VARCHAR(255) NULL,
          `land size` DECIMAL(10,2) NULL,
          `sensor_device_id` VARCHAR(80) NULL,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uq_users_email` (`email`),
          UNIQUE KEY `uq_users_sensor_device_id` (`sensor_device_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """

    with get_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(create_db_sql)
        conn.commit()

    with get_farmers_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            legacy_exists = table_exists(cursor, FARMERS_DATABASE, LEGACY_USER_TABLE)
            users_exists = table_exists(cursor, FARMERS_DATABASE, USER_TABLE)
            if legacy_exists and not users_exists:
                cursor.execute(
                    "RENAME TABLE {database}.{legacy_table} TO {database}.{user_table}".format(
                        database=quote_identifier(FARMERS_DATABASE),
                        legacy_table=quote_identifier(LEGACY_USER_TABLE),
                        user_table=quote_identifier(USER_TABLE),
                    )
                )
                logger.info("Renamed legacy farmers.%s table to %s", LEGACY_USER_TABLE, USER_TABLE)
            elif legacy_exists and users_exists:
                logger.warning("Legacy farmers.%s table still exists alongside %s; leaving it untouched", LEGACY_USER_TABLE, USER_TABLE)

            cursor.execute(create_user_sql)
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "location_type", "VARCHAR(20) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "district", "VARCHAR(120) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "city", "VARCHAR(120) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "village", "VARCHAR(120) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensor_device_id", "VARCHAR(80) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensors", "VARCHAR(20) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "pumps", "VARCHAR(20) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensor_setup_complete", "TINYINT(1) NOT NULL DEFAULT 0")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensor_setup_status", "VARCHAR(40) NULL")
            cursor.execute("UPDATE `users` SET `sensor_device_id` = NULL WHERE TRIM(COALESCE(`sensor_device_id`, '')) = ''")
            cursor.execute(
                """
                UPDATE `users` duplicate_user
                INNER JOIN (
                  SELECT `sensor_device_id`, MIN(`id`) AS keep_id
                  FROM `users`
                  WHERE `sensor_device_id` IS NOT NULL AND TRIM(`sensor_device_id`) <> ''
                  GROUP BY `sensor_device_id`
                  HAVING COUNT(*) > 1
                ) keepers ON duplicate_user.`sensor_device_id` = keepers.`sensor_device_id`
                SET
                  duplicate_user.`sensor_device_id` = NULL,
                  duplicate_user.`sensor_setup_complete` = 0,
                  duplicate_user.`sensor_setup_status` = 'pending'
                WHERE duplicate_user.`id` <> keepers.keep_id
                """
            )
            if not (
                index_exists(cursor, FARMERS_DATABASE, "users", "uq_users_sensor_device_id")
                or index_exists(cursor, FARMERS_DATABASE, "users", "uq_sign_in_sensor_device_id")
            ):
                cursor.execute("CREATE UNIQUE INDEX uq_users_sensor_device_id ON `users` (`sensor_device_id`)")
            modify_column_best_effort(cursor, "users", "password", "VARCHAR(255) NOT NULL")
            modify_column_best_effort(cursor, "users", "phone", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "name", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "state", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "location", "TEXT NULL")
            modify_column_best_effort(cursor, "users", "district", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "city", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "village", "VARCHAR(512) NULL")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  email VARCHAR(255) NOT NULL,
                  token_hash CHAR(64) NOT NULL,
                  expires_at TIMESTAMP NOT NULL,
                  used_at TIMESTAMP NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_reset_token_hash (token_hash),
                  INDEX idx_reset_email_created (email, created_at),
                  INDEX idx_reset_expires (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        conn.commit()


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
        "name": name,
        "email": email,
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


def ensure_public_rate_limit_table() -> None:
    global PUBLIC_RATE_TABLE_READY
    if PUBLIC_RATE_TABLE_READY:
        return
    database = DB_CONFIG["database"]
    with get_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public_rate_limits (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  bucket VARCHAR(80) NOT NULL,
                  client_host VARCHAR(255) NOT NULL,
                  requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_rate_bucket_client_time (bucket, client_host, requested_at),
                  INDEX idx_rate_requested_at (requested_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        conn.commit()
    PUBLIC_RATE_TABLE_READY = True


def run_database_migrations() -> None:
    ensure_sensor_tables()
    ensure_farmers_tables()
    ensure_public_rate_limit_table()


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


def set_auth_cookie(response: Response, token: str) -> str:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
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
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        path="/",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
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
    if api_key_matches(x_api_key, api_key, device_id):
        return

    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    if not owner_device_id or owner_device_id != device_id:
        raise HTTPException(status_code=403, detail="Sensor device does not belong to this account")


def auth_token_for_user(user: dict[str, Any]) -> str:
    return sign_auth_token({"user_id": user["id"], "email": user["email"]})


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

    cached_for_lang = TRANSLATION_CACHE.setdefault(target, {})
    missing = [text for text in texts if text and text not in cached_for_lang]

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

            for source, translated in zip(missing, translated_items):
                cached_for_lang[source] = str(translated)
        except HTTPException:
            raise
        except Exception as exc:
            raise_public_error(502, "Translation failed", "Translation request failed", exc)

    return [cached_for_lang.get(text, text) for text in texts]


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


@app.get("/api/public/sensors/latest")
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


def owner_profile_context(owner_id: int) -> dict[str, Any]:
    try:
        with get_farmers_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM `users` WHERE `id` = %s LIMIT 1", (owner_id,))
                row = cursor.fetchone()
    except Exception as exc:
        raise_public_error(503, "Could not load account profile", "Owner profile lookup failed", exc)

    return user_row_to_payload(row) if row else {}


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


@app.get("/api/health")
def health():
    try:
      with get_connection() as conn:
          conn.ping(reconnect=True, attempts=1, delay=0)
      with get_farmers_connection() as farmers_conn:
          farmers_conn.ping(reconnect=True, attempts=1, delay=0)
      return {"ok": True, "database": "connected", "farmers_database": FARMERS_DATABASE}
    except Exception as exc:
      raise_public_error(503, "Database not connected", "Health check failed", exc)


@app.get("/")
def root():
    return {
        "service": "CropConnect ESP32 Ingestion API",
        "docs": "/docs",
        "health": "/api/health",
        "esp32_relay_command": "/api/esp32/relay-command",
        "hardware_flow": "Main ESP32 uses SIM800L to ingest sensors and poll pump commands, then forwards commands to the pump ESP32.",
    }


@app.get("/api/esp32/relay-command", response_class=PlainTextResponse)
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


@app.get("/esp32/relay-command", response_class=PlainTextResponse)
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


@app.post("/api/esp32/relay-status")
def esp32_relay_status(
    payload: RelayStatusIn,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    check_api_key(x_api_key, api_key, payload.device_id)
    states = parse_relay_states(payload.relays)

    update_relay_applied_state(states)
    save_relay_applied_states_to_db(payload.device_id, states)
    desired_states = sync_relay_commands_from_db(payload.device_id)
    return {
        "ok": True,
        "device_id": payload.device_id,
        "status": relay_status_payload_from_db(payload.device_id, desired_states),
    }


@app.get("/api/esp32/relay-status/update")
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
    update_relay_applied_state(states)
    save_relay_applied_states_to_db(device_id, states)
    desired_states = sync_relay_commands_from_db(device_id)
    return {"ok": True, "status": relay_status_payload_from_db(device_id, desired_states)}


@app.get("/api/esp32/relay-status")
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


@app.post("/api/telemetry/ingest")
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


@app.get("/api/telemetry/ingest")
def ingest_telemetry_get(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    return ingest_telemetry_from_query(request, x_api_key, api_key)


@app.post("/data")
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


@app.get("/data")
def receive_get(
    request: Request,
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None, max_length=120),
):
    require_esp32_get_write_enabled()
    return ingest_telemetry_from_query(request, x_api_key, api_key)


@app.get("/api/sensors/latest")
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


@app.get("/api/esp32/device-key")
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


@app.post("/api/esp32/device-key")
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


@app.post("/api/esp32/device-key/rotate")
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


@app.get("/api/sensors/history")
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


@app.post("/api/auth/signup")
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
          `land size`,
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
        "csrfToken": csrf_token,
    }


@app.post("/api/auth/login")
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
        "csrfToken": csrf_token,
    }


@app.post("/api/auth/logout")
def auth_logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@app.get("/api/auth/csrf")
def auth_csrf(
    response: Response,
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    require_auth_owner(None, auth_cookie)
    csrf_token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, csrf_token)
    return {"ok": True, "csrfToken": csrf_token}


@app.get("/api/auth/profile")
def auth_profile(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    user = owner_profile_context(owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": user}


@app.post("/api/auth/password-reset-request")
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
                            f"{FRONTEND_PUBLIC_URL}/reset-password?"
                            + urllib.parse.urlencode({"email": email, "token": reset_token})
                        )
                        cursor.execute(
                            """
                            INSERT INTO password_reset_tokens (email, token_hash, expires_at)
                            VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE))
                            """,
                            (email, token_hash(reset_token), PASSWORD_RESET_TOKEN_TTL_MINUTES),
                        )
                        reset_token_id = cursor.lastrowid
                        conn.commit()
                        try:
                            send_password_reset_email(email, reset_url)
                        except Exception as exc:
                            cursor.execute(
                                "UPDATE password_reset_tokens SET used_at = UTC_TIMESTAMP() WHERE id = %s",
                                (reset_token_id,),
                            )
                            conn.commit()
                            logger.exception("Password reset email delivery failed: %s", exc)
                    conn.commit()
        except Exception as exc:
            logger.exception("Password reset request failed: %s", exc)
    else:
        logger.info("Password reset request received, but SMTP is not configured.")

    return {
        "ok": True,
        "message": "If an account exists, password reset instructions will be sent.",
    }


@app.post("/api/auth/password-reset-confirm")
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


@app.post("/api/auth/profile")
def auth_profile_update(
    payload: AuthProfileUpdateIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)

    updates: list[str] = []
    values: list[Any] = []
    field_map = {
        "name": ("name", "`name` = %s"),
        "phone": ("phone", "`phone` = %s"),
        "state": ("state", "`state` = %s"),
        "location": ("location", "`location` = %s"),
        "land_size": ("land size", "`land size` = %s"),
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


@app.post("/api/pump/state")
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


@app.post("/api/farm/pump-state")
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


@app.get("/api/farm/pump-states")
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


@app.post("/api/farm/timers")
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
                            raise HTTPException(status_code=400, detail="Timer duration must be a number")
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


@app.get("/api/farm/timers")
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


@app.get("/api/farm/chat-history")
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


@app.post("/api/farm/snapshot")
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


@app.get("/api/farm/snapshot/latest")
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


@app.post("/api/utils/translate")
async def api_translate(payload: TranslateIn, request: Request):
    if not PUBLIC_TRANSLATION_ENABLED:
        raise HTTPException(status_code=503, detail="Public translation endpoint is disabled")
    rate_limit_public_request(request, "translate", limit=30, window_seconds=60)
    texts = payload.texts or ([payload.text] if payload.text else [])
    texts = [text for text in texts if text is not None]
    if not texts:
        raise HTTPException(status_code=422, detail="Provide text or texts to translate")

    translated = translate_texts_with_ai(texts, payload.target_lang)
    response = {
        "ok": True,
        "target_lang": payload.target_lang,
        "translations": translated,
    }
    if payload.text is not None and payload.texts is None:
        response["translated"] = translated[0]
    return response


@app.post("/api/enquiries")
def enquiries(payload: EnquiryIn, request: Request):
    rate_limit_public_request(request, "enquiries", limit=5, window_seconds=300)
    if not smtp_configured():
        raise HTTPException(status_code=503, detail="Email delivery is not configured")
    try:
        send_enquiry_email(payload)
    except Exception as exc:
        raise_public_error(502, "Email delivery failed", "Enquiry email delivery failed", exc)

    return {
        "ok": True,
        "message": "Enquiry received",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/ai/chat")
def ai_chat(
    payload: ChatIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-chat", limit=20, window_seconds=60)
    try:
        related_to_plant_or_soil = classify_farm_scope_with_ai(payload.message, payload.language)
    except Exception as exc:
        raise_public_error(502, "AI scope check failed", "AI chat scope classifier failed", exc)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    live_sensor_context = latest_sensor_context(device_id)
    live_sensor_data = live_sensor_context.get("sensor_data") or {}
    profile_location = ", ".join(
        item
        for item in [
            owner_profile.get("village") or owner_profile.get("city") or owner_profile.get("location"),
            owner_profile.get("district"),
            owner_profile.get("state"),
        ]
        if item
    )
    live_market_data = live_market_context_for_profile(owner_profile) if is_market_question(payload.message) else {}

    if not related_to_plant_or_soil:
        reply = (
            "I can only help with farm, crop, soil, irrigation, sensor, weather, pest, fertilizer, pump, "
            "or mandi topics. Ask me something like: which crop fits my latest soil readings?"
        )
        insert_chat_record(owner_id, owner_email, "user", payload.message, False, live_sensor_data, profile_location)
        insert_chat_record(owner_id, owner_email, "bot", reply, False, live_sensor_data, profile_location)
        return {
            "ok": True,
            "source": "scope_filter",
            "reply": reply,
            "related_to_plant_or_soil": False,
            "used_sensor_data": live_sensor_data,
            "sensor_source": live_sensor_context.get("source"),
            "sensor_recorded_at": live_sensor_context.get("recorded_at"),
            "sensor_message": live_sensor_context.get("message", ""),
            "used_google_search": False,
        }

    context = {
        "location": profile_location,
        "language": payload.language,
        "account": {
            "id": owner_id,
            "email": owner_email,
            "name": owner_profile.get("name") or "",
            "state": owner_profile.get("state") or "",
            "district": owner_profile.get("district") or "",
            "city": owner_profile.get("city") or "",
            "village": owner_profile.get("village") or "",
            "land_size": owner_profile.get("landSize"),
        },
        "live_sensor_context": live_sensor_context,
        "dashboard_sensor_data": {},
        "market_data": live_market_data,
        "weather_data": {},
    }
    search_results = google_search(payload.message, profile_location) if related_to_plant_or_soil else []

    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for AI chatbot answers")

    messages = [
        {
            "role": "developer",
            "content": (
                "You are CropConnect's farming assistant for an IoT farming dashboard. "
                "Your scope is crops, soil, irrigation, sensors, weather, pests/diseases, fertilizer, pumps, and market/mandi decisions. "
                "Never answer questions outside that farming scope. For unrelated questions, briefly say you can only help with farm, crop, soil, irrigation, sensor, weather, pest, fertilizer, pump, or mandi topics, then offer one farming question the user can ask. "
                "Always answer the latest user question directly; never repeat or continue an older answer unless the latest question clearly asks for a follow-up. "
                "Give concise, practical guidance with simple language, short paragraphs, and clear next steps. "
                "Prefer 2-5 actionable points over long explanations. Use live_sensor_context as the primary source for sensor readings because it is loaded from the latest MySQL ESP32 row. Use dashboard_sensor_data only as secondary context. "
                "Treat null, missing, empty, unavailable, or -- sensor values as unknown, never as zero. If live sensor data is unavailable, say that and explain what reading is needed. "
                "Use market_data for mandi questions only when recordsCount is greater than 0. If market_data is empty or unavailable, say live mandi prices are unavailable instead of guessing. "
                "Do not invent sensor readings, market prices, weather facts, crop disease certainty, or chemical dosages. "
                "If a question needs certified agronomy, veterinary, legal, medical, or financial advice, say so clearly. "
                "When web search results are supplied, use them as supporting context and mention that the "
                "answer is based on the available search snippets, not direct Google pages. "
                "Always answer in the user's selected language (" + LANGUAGE_NAMES.get(selected_language(payload), payload.language) + ") only. "
                "If the user's spoken or typed message is in another language, understand it, "
                "but reply only in the selected language, not in the input language."
            ),
        },
        {"role": "user", "content": "Current CropConnect dashboard context: " + json.dumps(context, ensure_ascii=False, default=str)},
    ]
    if search_results:
        messages.append(
            {
                "role": "user",
                "content": "Google search context: " + str(search_results),
            }
        )
    if payload.history:
        messages.append(
            {
                "role": "user",
                "content": "Earlier chat history below is context only. Do not answer it unless the latest question asks for a follow-up.",
            }
        )
    for item in payload.history[-4:]:
        role = "assistant" if item.get("type") == "bot" else "user"
        text = item.get("text", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({
        "role": "user",
        "content": (
            "Answer this latest question only. Desired reply language: "
            + LANGUAGE_NAMES.get(selected_language(payload), payload.language)
            + ". Input language: "
            + payload.input_language
            + ". Latest question: "
            + payload.message
        ),
    })

    try:
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": messages,
                "temperature": 0.25,
                "max_tokens": 600,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
    except Exception as exc:
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        raise_public_error(502, "AI chatbot request failed", "AI chatbot request failed", exc)

    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not reply:
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        raise HTTPException(status_code=502, detail="AI chatbot returned an empty answer")

    final_reply = reply
    insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
    insert_chat_record(owner_id, owner_email, "bot", final_reply, related_to_plant_or_soil, live_sensor_data, profile_location)
    return {
        "ok": True,
        "related_to_plant_or_soil": related_to_plant_or_soil,
        "reply": final_reply,
        "sensor_source": live_sensor_context.get("source"),
        "sensor_recorded_at": live_sensor_context.get("recorded_at"),
        "sensor_message": live_sensor_context.get("message", ""),
        "used_google_search": bool(search_results),
    }


@app.post("/api/crops/recommend")
def crop_recommend(
    payload: CropRecommendIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-crop-recommend", limit=8, window_seconds=15 * 60)
    require_openai()

    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    requested_device_id = str(payload.device_id or "").strip()
    if not owner_device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")
    if requested_device_id and requested_device_id != owner_device_id:
        raise HTTPException(status_code=403, detail="Sensor device does not belong to this account")

    device_id = owner_device_id
    live_sensor_context = latest_sensor_context(device_id)
    live_sensor_data = live_sensor_context.get("sensor_data") or {}
    profile_location = ", ".join(
        item
        for item in [
            owner_profile.get("village") or owner_profile.get("city") or owner_profile.get("location"),
            owner_profile.get("district"),
            owner_profile.get("state"),
        ]
        if item
    )
    context = {
        "soil_moisture": live_sensor_data.get("soil_moisture"),
        "humidity": live_sensor_data.get("humidity"),
        "temperature": live_sensor_data.get("temperature"),
        "ph": live_sensor_data.get("ph"),
        "nitrogen": live_sensor_data.get("nitrogen"),
        "phosphorus": live_sensor_data.get("phosphorus"),
        "potassium": live_sensor_data.get("potassium"),
        "goal": payload.goal,
        "location": profile_location,
        "acreage": owner_profile.get("landSize"),
        "season": payload.season,
        "language": payload.language,
        "device_id": device_id,
        "sensor_source": live_sensor_context.get("source"),
        "sensor_recorded_at": live_sensor_context.get("recorded_at"),
        "sensor_message": live_sensor_context.get("message"),
    }
    missing_readings = missing_crop_readings(context)
    if not has_core_sensor_context(context):
        return {
            "ok": True,
            "source": "no_live_sensor_data",
            "model": None,
            "crops": [],
            "summary": "",
            "missing_readings": missing_readings,
            "sensor_context": live_sensor_context,
        }

    try:
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": build_crop_recommendation_messages(context),
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = parse_ai_json(raw)
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "AI crop recommendation failed", "AI crop recommendation request failed", exc)

    crops = parsed.get("crops") if isinstance(parsed, dict) else None
    if not isinstance(crops, list):
        raise HTTPException(status_code=502, detail="AI crop recommendation returned invalid data")

    return {
        "ok": True,
        "source": "openai",
        "model": OPENAI_MODEL,
        "crops": crops,
        "summary": parsed.get("summary", "") if isinstance(parsed, dict) else "",
        "missing_readings": missing_readings,
        "sensor_context": live_sensor_context,
    }


@app.post("/api/ai/orchestrate")
def ai_orchestrate(
    payload: AIOrchestrateIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-orchestrate", limit=8, window_seconds=15 * 60)
    require_openai()

    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    context = {
        "objective": payload.objective,
        "language": payload.language,
        "account": {
            "id": owner_id,
            "email": owner_email,
            "name": owner_profile.get("name") or "",
            "state": owner_profile.get("state") or "",
            "district": owner_profile.get("district") or "",
            "city": owner_profile.get("city") or "",
            "village": owner_profile.get("village") or "",
            "land_size": owner_profile.get("landSize"),
            "sensor_device_id": device_id,
        },
        "live_sensor_context": latest_sensor_context(device_id),
    }
    prompt = (
        "You are CropConnect's farm operations orchestrator. Analyze live sensor data, pump state, timers, "
        "weather, market context, and farmer objective. Return strict JSON only. "
        "Never directly actuate pumps or hardware. Any pump or irrigation change must be an action with "
        "\"requires_confirmation\": true. Keep advice practical and safety-first. "
        "JSON shape: {\"summary\":\"...\",\"risk_level\":\"low/medium/high\","
        "\"insights\":[\"...\"],\"actions\":[{\"id\":\"short-id\",\"title\":\"...\","
        "\"type\":\"pump|timer|crop|market|sensor|profile\",\"priority\":\"low/medium/high\","
        "\"requires_confirmation\":true,\"payload\":{},\"reason\":\"...\"}],"
        "\"questions\":[\"...\"]}."
    )

    try:
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
                ],
                "temperature": 0.15,
                "max_tokens": 1200,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = parse_ai_json(raw)
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "AI orchestration failed", "AI orchestration request failed", exc)

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="AI orchestration returned invalid data")

    for action in parsed.get("actions", []) if isinstance(parsed.get("actions"), list) else []:
        if isinstance(action, dict) and action.get("type") in {"pump", "timer"}:
            action["requires_confirmation"] = True

    return {
        "ok": True,
        "source": "openai",
        "model": OPENAI_MODEL,
        "plan": parsed,
    }


def weather_code_condition(value: Any) -> dict[str, str]:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return {"condition": "--", "advice": ""}

    if code == 0:
        return {"condition": "Clear", "advice": "Good field-work window if sensor readings are normal."}
    if code in {1, 2, 3}:
        return {"condition": "Cloudy", "advice": "Check humidity before spraying or fertilizer application."}
    if code in {45, 48}:
        return {"condition": "Fog", "advice": "Wait for visibility and leaf surface to improve before spraying."}
    if code in {51, 53, 55, 56, 57}:
        return {"condition": "Drizzle", "advice": "Delay spraying and review irrigation need after rainfall."}
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return {"condition": "Rain", "advice": "Pause irrigation and check drainage after the rain ends."}
    if code in {71, 73, 75, 77, 85, 86}:
        return {"condition": "Snow", "advice": "Protect sensitive crops and avoid unnecessary irrigation."}
    if code in {95, 96, 99}:
        return {"condition": "Storm", "advice": "Avoid field operations and secure pump/electrical equipment."}
    return {"condition": "--", "advice": ""}


def market_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text in {"", "--", "NA", "N/A", "null", "None"} else text


def market_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if not number.is_integer():
        return round(number, 2)
    return int(number)


def market_record_value(record: dict[str, Any], *names: str) -> Any:
    normalized = {
        re.sub(r"[^a-z0-9]", "", str(key).lower()): value
        for key, value in record.items()
    }
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if key in normalized:
            return normalized[key]
    return None


def normalize_market_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": market_text(market_record_value(record, "state")),
        "district": market_text(market_record_value(record, "district")),
        "market": market_text(market_record_value(record, "market")),
        "commodity": market_text(market_record_value(record, "commodity")),
        "variety": market_text(market_record_value(record, "variety")),
        "grade": market_text(market_record_value(record, "grade")),
        "arrivalDate": market_text(market_record_value(record, "arrival_date", "arrival date", "arrivaldate")),
        "minPrice": market_number(market_record_value(record, "min_price", "min price", "minprice")),
        "maxPrice": market_number(market_record_value(record, "max_price", "max price", "maxprice")),
        "modalPrice": market_number(market_record_value(record, "modal_price", "modal price", "modalprice")),
    }


def market_record_has_price(record: dict[str, Any]) -> bool:
    return any(record.get(key) is not None for key in ("minPrice", "maxPrice", "modalPrice"))


def market_payload_from_records(
    records: list[dict[str, Any]],
    requested_state: str,
    requested_location: str,
    matched_district: str = "",
    message: str = "",
) -> dict[str, Any]:
    prices = [
        item
        for item in (normalize_market_record(record) for record in records if isinstance(record, dict))
        if item.get("commodity") and item.get("market") and market_record_has_price(item)
    ]

    mandi_groups: dict[str, dict[str, Any]] = {}
    for item in prices:
        key = "|".join([item.get("market") or "", item.get("district") or ""])
        group = mandi_groups.setdefault(
            key,
            {
                "name": item.get("market") or "--",
                "district": item.get("district") or "",
                "state": item.get("state") or requested_state,
                "commodities": [],
            },
        )
        if len(group["commodities"]) < 6:
            group["commodities"].append(
                {
                    "commodity": item.get("commodity") or "--",
                    "modalPrice": item.get("modalPrice"),
                    "minPrice": item.get("minPrice"),
                    "maxPrice": item.get("maxPrice"),
                    "arrivalDate": item.get("arrivalDate") or "",
                }
            )

    return {
        "ok": True,
        "source": "Data.gov.in live Agmarknet mandi prices",
        "sourceUrl": DATA_GOV_MARKET_RESOURCE_URL,
        "requestedState": requested_state,
        "requestedLocation": requested_location,
        "matchedDistrict": matched_district,
        "recordsCount": len(prices),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "message": message or ("No live mandi records found for this location." if not prices else ""),
        "prices": prices[:60],
        "mandis": list(mandi_groups.values())[:12],
    }


def data_gov_market_records(state: str, district: str = "", commodity: str = "") -> list[dict[str, Any]]:
    params = {
        "api-key": DATA_GOV_API_KEY,
        "format": "json",
        "limit": str(MARKET_PRICE_LIMIT),
        "offset": "0",
        "filters[State]": state,
    }
    if district:
        params["filters[District]"] = district
    if commodity:
        params["filters[Commodity]"] = commodity

    url = f"{DATA_GOV_MARKET_RESOURCE_URL}?{urllib.parse.urlencode(params)}"
    payload = request_json(url)
    records = payload.get("records") if isinstance(payload, dict) else []
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def user_market_location(profile: dict[str, Any]) -> tuple[str, str, str]:
    state = market_text(profile.get("state"))
    district = market_text(profile.get("district"))
    location_type = str(profile.get("locationType") or profile.get("location_type") or "").strip().lower()
    primary_place = profile.get("village") if location_type == "village" else profile.get("city")
    fallback_place = profile.get("city") or profile.get("village") or profile.get("location")
    place = market_text(primary_place or fallback_place)
    location_parts = [place]
    if district and district.lower() != place.lower():
        location_parts.append(district)
    location_parts.append(state)
    requested_location = ", ".join([part for part in location_parts if part])
    return state, district or place, requested_location


def live_market_context_for_profile(profile: dict[str, Any]) -> dict[str, Any]:
    state, district_candidate, requested_location = user_market_location(profile)
    if not state:
        return market_payload_from_records(
            [],
            "",
            requested_location,
            message="State is missing from the user profile, so local mandi prices cannot be loaded.",
        )
    if not DATA_GOV_API_KEY:
        return market_payload_from_records(
            [],
            state,
            requested_location,
            message="DATA_GOV_API_KEY is not configured, so live mandi prices are unavailable.",
        )

    try:
        records = []
        matched_district = ""
        message = ""
        if district_candidate:
            records = data_gov_market_records(state, district_candidate)
            matched_district = district_candidate if records else ""
        if not records:
            records = data_gov_market_records(state)
            if district_candidate and records:
                message = (
                    f"No district-level mandi records found for {district_candidate}; "
                    "showing latest state-level records."
                )
        return market_payload_from_records(records, state, requested_location, matched_district, message)
    except Exception as exc:
        log_backend_error("Data.gov mandi context failed", exc)
        return market_payload_from_records(
            [],
            state,
            requested_location,
            message="Live mandi feed is currently unavailable.",
        )


def build_market_insight_messages(context: dict[str, Any], language: str | None, objective: str) -> list[dict[str, str]]:
    return [
        {
            "role": "developer",
            "content": (
                "You are CropConnect's AI market analyst for farmers. Analyze only the supplied live mandi records, "
                "profile, and sensor context. Do not invent prices, markets, demand, weather, crop stock, or exact profit. "
                "If recordsCount is 0 or live prices are unavailable, return a summary saying live market data is unavailable "
                "and keep recommendations empty. Treat null, empty, unavailable, and -- values as unknown, never as zero. "
                "Return strict JSON only with this shape: "
                "{\"summary\":\"short farmer-ready summary\","
                "\"recommendations\":[{\"title\":\"short title\",\"action\":\"what to do\",\"reason\":\"why from data\",\"confidence\":\"low|medium|high\"}],"
                "\"watch\":[\"short risk or thing to monitor\"]}. "
                "Keep recommendations practical and cautious, not financial certainty. "
                f"Answer in {selected_language_name(language)}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objective": objective,
                    "context": context,
                },
                ensure_ascii=False,
                default=str,
            ),
        },
    ]


def normalize_market_insight_payload(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise ValueError("AI market insight returned non-object JSON")

    recommendations = parsed.get("recommendations")
    if not isinstance(recommendations, list):
        recommendations = []
    cleaned_recommendations = []
    for item in recommendations[:5]:
        if not isinstance(item, dict):
            continue
        cleaned_recommendations.append(
            {
                "title": market_text(item.get("title")) or "--",
                "action": market_text(item.get("action")) or "--",
                "reason": market_text(item.get("reason")) or "--",
                "confidence": market_text(item.get("confidence")) or "low",
            }
        )

    watch = parsed.get("watch")
    if not isinstance(watch, list):
        watch = []

    return {
        "summary": market_text(parsed.get("summary")),
        "recommendations": cleaned_recommendations,
        "watch": [market_text(item) for item in watch[:5] if market_text(item)],
    }


@app.get("/api/market/prices")
def market_prices(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    commodity: str = Query(default="", max_length=80),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "market-prices", limit=20, window_seconds=60)

    if not DATA_GOV_API_KEY:
        raise HTTPException(status_code=503, detail="Live mandi price feed is not configured")

    profile = owner_profile_context(owner_id)
    state, district_candidate, requested_location = user_market_location(profile)
    if not state:
        raise HTTPException(status_code=400, detail="Add your state in profile to load local mandi prices")

    requested_commodity = market_text(commodity)
    matched_district = ""
    message = ""
    try:
        records = []
        if district_candidate:
            records = data_gov_market_records(state, district_candidate, requested_commodity)
            matched_district = district_candidate if records else ""
        if not records:
            records = data_gov_market_records(state, "", requested_commodity)
            if district_candidate and records:
                message = (
                    f"No district-level mandi records found for {district_candidate}; "
                    "showing latest state-level records."
                )
    except Exception as exc:
        raise_public_error(502, "Market price request failed", "Data.gov mandi request failed", exc)

    return market_payload_from_records(records, state, requested_location, matched_district, message)


@app.post("/api/market/insights")
def market_insights(
    payload: MarketInsightIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-market-insights", limit=6, window_seconds=15 * 60)
    require_openai()

    if not DATA_GOV_API_KEY:
        raise HTTPException(status_code=503, detail="Live mandi price feed is not configured")

    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    market_context = live_market_context_for_profile(owner_profile)
    live_sensor_context = latest_sensor_context(device_id) if device_id else {
        "source": "unavailable",
        "sensor_data": {},
        "message": "No sensor device is configured for this account.",
    }

    if not market_context.get("recordsCount"):
        return {
            "ok": True,
            "source": "no_live_market_data",
            "model": None,
            "summary": market_context.get("message") or "Live mandi prices are unavailable for this location.",
            "recommendations": [],
            "watch": [],
            "market_data": market_context,
            "sensor_context": live_sensor_context,
        }

    context = {
        "account": {
            "state": owner_profile.get("state") or "",
            "district": owner_profile.get("district") or "",
            "city": owner_profile.get("city") or "",
            "village": owner_profile.get("village") or "",
            "land_size": owner_profile.get("landSize"),
        },
        "market_data": market_context,
        "live_sensor_context": live_sensor_context,
    }

    try:
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": build_market_insight_messages(context, payload.language, payload.objective),
                "temperature": 0.2,
                "max_tokens": 800,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        insight = normalize_market_insight_payload(parse_ai_json(raw))
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "AI market insight failed", "AI market insight request failed", exc)

    return {
        "ok": True,
        "source": "openai_with_live_market_data",
        "model": OPENAI_MODEL,
        **insight,
        "market_data": market_context,
        "sensor_context": live_sensor_context,
    }


@app.get("/api/weather/forecast")
def weather_forecast(request: Request, location: str = Query(default="", max_length=160)):
    rate_limit_public_request(request, "weather", limit=60, window_seconds=60)
    if not location:
        raise HTTPException(status_code=400, detail="location is required")
    try:
        # Geocoding using Open-Meteo (free)
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": location, "count": 1, "language": "en", "format": "json"}
        )
        geo = request_json(geo_url)
        result = (geo.get("results") or [None])[0]
        if not result and "," in location:
            city_name = location.split(",", 1)[0].strip()
            geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
                {"name": city_name, "count": 1, "language": "en", "format": "json"}
            )
            geo = request_json(geo_url)
            result = (geo.get("results") or [None])[0]
        if not result:
            raise HTTPException(status_code=404, detail="Location not found")

        # Open-Meteo provides live internet forecast data without requiring an API key.
        params = {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl,precipitation,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
            "forecast_days": 7,
            "timezone": "auto",
        }
        forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
        data = request_json(forecast_url)
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "Weather request failed", "Weather request failed", exc)

    current = data.get("current", {})
    daily = data.get("daily", {})
    days = daily.get("time", [])
    rain = daily.get("precipitation_probability_max", [])
    rain_amount = daily.get("precipitation_sum", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    daily_weather_codes = daily.get("weather_code", [])
    current_condition = weather_code_condition(current.get("weather_code"))

    def rounded_number(value: Any, digits: int = 0) -> float | int | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        rounded = round(number, digits)
        return int(rounded) if digits == 0 else rounded

    def list_number(values: list[Any], index: int, digits: int = 0) -> float | int | None:
        if index >= len(values):
            return None
        return rounded_number(values[index], digits)

    def rainfall_condition(probability: Any) -> str:
        value = rounded_number(probability)
        if value is None:
            return "--"
        if value >= 50:
            return "Rain"
        if value >= 25:
            return "Cloud"
        return "Clear"

    return {
        "ok": True,
        "source": "Open-Meteo live internet forecast",
        "requested_location": location,
        "location": {
            "name": result.get("name"),
            "admin1": result.get("admin1"),
            "country": result.get("country"),
            "latitude": result.get("latitude"),
            "longitude": result.get("longitude"),
        },
        "temp": rounded_number(current.get("temperature_2m")),
        "condition": current_condition["condition"],
        "advice": current_condition["advice"],
        "humidity": rounded_number(current.get("relative_humidity_2m")),
        "wind": rounded_number(current.get("wind_speed_10m")),
        "pressure": rounded_number(current.get("pressure_msl")),
        "rainfall": [
            {
                "day": "Today" if index == 0 else datetime.fromisoformat(day).strftime("%a"),
                "date": day,
                "value": list_number(rain, index),
                "mm": list_number(rain_amount, index, 1),
            }
            for index, day in enumerate(days[:7])
        ],
        "forecast": [
            {
                "day": "Today" if index == 0 else datetime.fromisoformat(day).strftime("%a"),
                "icon": weather_code_condition(daily_weather_codes[index] if index < len(daily_weather_codes) else None)["condition"],
                "high": list_number(highs, index),
                "low": list_number(lows, index),
            }
            for index, day in enumerate(days)
        ],
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=env("HOST", "0.0.0.0"), port=int(env("PORT", "8001")))
