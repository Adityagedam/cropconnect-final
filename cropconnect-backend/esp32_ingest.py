# Backwards-compatible API entrypoint that wires the FastAPI app and re-exports shared helpers.
import secrets
import sys
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

import crop_ai_agent
import db_utils
import models
import security_crypto
from config import settings
from db import migrations as db_migrations
from db.connections import configure_connections, get_connection
from logging_config import configure_logging
from routers import ai as ai_router
from routers import auth as auth_router
from routers import farm as farm_router
from routers import market as market_router
from routers import public as public_router
from routers import pumps as pumps_router
from routers import sensors as sensors_router
from routers import weather as weather_router
from services import (
    ai_service,
    auth_service,
    email_service,
    esp32_service,
    market_service,
    sensor_service,
)
from services import (
    rate_limit as rate_limit_service,
)

logger = configure_logging()
security_crypto.require_data_secret()

if settings.mysql_public_url:
    url = urlparse(settings.mysql_public_url)
    DB_CONFIG = {
        "host": url.hostname,
        "port": int(url.port or 3306),
        "user": url.username,
        "password": url.password,
        "database": url.path[1:] or "railway",
    }
else:
    DB_CONFIG = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "database": settings.mysql_database,
    }

FARMERS_DATABASE = settings.mysql_farmers_database
MYSQL_POOL_SIZE = max(1, settings.mysql_pool_size)
configure_connections(DB_CONFIG, FARMERS_DATABASE, MYSQL_POOL_SIZE)

API_KEY = settings.esp32_api_key
ALLOW_GLOBAL_ESP32_API_KEY = settings.allow_global_esp32_api_key
CONTACT_TO_EMAIL = settings.contact_to_email
OPENAI_API_KEY = settings.openai_api_key
OPENAI_MODEL = settings.openai_model
GOOGLE_API_KEY = settings.google_api_key
GOOGLE_CSE_ID = settings.google_cse_id
DATA_GOV_API_KEY = settings.data_gov_api_key
DATA_GOV_MARKET_RESOURCE_URL = settings.data_gov_market_resource_url
MARKET_PRICE_LIMIT = settings.market_price_limit
PUBLIC_LANDING_SENSOR_DEVICE_ID = settings.public_landing_sensor_device_id
PUBLIC_TRANSLATION_ENABLED = settings.public_translation_enabled
QUERY_API_KEY_ENABLED = settings.query_api_key_enabled
ESP32_GET_WRITE_ENABLED = settings.esp32_get_write_enabled
PASSWORD_RESET_TOKEN_TTL_MINUTES = settings.password_reset_token_ttl_minutes
FRONTEND_PUBLIC_URL = settings.frontend_public_url.rstrip("/")
AUTH_COOKIE_NAME = auth_service.AUTH_COOKIE_NAME
CSRF_COOKIE_NAME = auth_service.CSRF_COOKIE_NAME
CSRF_HEADER_NAME = "x-csrf-token"
AUTH_COOKIE_SECURE = settings.auth_cookie_secure
AUTH_COOKIE_SAMESITE = settings.auth_cookie_samesite
AUTH_COOKIE_MAX_AGE_SECONDS = auth_service.AUTH_COOKIE_MAX_AGE_SECONDS
PUBLIC_RATE_LIMITS = rate_limit_service.PUBLIC_RATE_LIMITS
PUBLIC_RATE_LIMIT_DB_FAIL_OPEN = rate_limit_service.PUBLIC_RATE_LIMIT_DB_FAIL_OPEN
TRUST_PROXY_HEADERS = settings.trust_proxy_headers
USER_TABLE = "users"
LEGACY_USER_TABLE = "sign-in"
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in settings.frontend_origins.split(",")
    if origin.strip()
]
if "*" in FRONTEND_ORIGINS:
    raise RuntimeError("FRONTEND_ORIGINS cannot contain '*' when credentialed auth cookies are enabled")

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


def run_database_migrations() -> None:
    db_migrations.run_database_migrations(sys.modules[__name__])


def public_client_host(request: Request) -> str:
    return rate_limit_service.public_client_host(request)


def rate_limit_public_request(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    rate_limit_service.rate_limit_public_request(request, bucket, limit, window_seconds)


def rate_limit_authenticated_request(owner_id: int, bucket: str, limit: int, window_seconds: int) -> None:
    rate_limit_service.rate_limit_authenticated_request(owner_id, bucket, limit, window_seconds)


def rate_limit_named_key(bucket: str, client_key: str, limit: int, window_seconds: int) -> None:
    rate_limit_service.get_connection = get_connection
    rate_limit_service.PUBLIC_RATE_LIMIT_DB_FAIL_OPEN = PUBLIC_RATE_LIMIT_DB_FAIL_OPEN
    rate_limit_service.rate_limit_named_key(bucket, client_key, limit, window_seconds)


def register_routers() -> None:
    app.include_router(public_router.router)
    app.include_router(auth_router.router)
    app.include_router(sensors_router.router)
    app.include_router(pumps_router.router)
    app.include_router(farm_router.router)
    app.include_router(market_router.router)
    app.include_router(weather_router.router)
    app.include_router(ai_router.router)


_EXPORT_MODULES = (
    models,
    db_utils,
    security_crypto,
    crop_ai_agent,
    ai_service,
    auth_service,
    email_service,
    esp32_service,
    market_service,
    sensor_service,
    weather_router,
    pumps_router,
    public_router,
)


def __getattr__(name: str):
    if name == "HTTPException":
        from fastapi import HTTPException

        return HTTPException
    if name == "request_json":
        from http_client import request_json

        return request_json
    for module in _EXPORT_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


register_routers()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
