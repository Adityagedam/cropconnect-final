# FastAPI application creation, middleware, and router registration.
import secrets
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from config import settings
from logging_config import request_id_var
from routers import ai as ai_router
from routers import auth as auth_router
from routers import farm as farm_router
from routers import market as market_router
from routers import public as public_router
from routers import pumps as pumps_router
from routers import sensors as sensors_router
from routers import weather as weather_router
from services.auth_service import AUTH_COOKIE_NAME, CSRF_COOKIE_NAME

CSRF_HEADER_NAME = "x-csrf-token"
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in settings.frontend_origins.split(",")
    if origin.strip()
]
if "*" in FRONTEND_ORIGINS:
    raise RuntimeError("FRONTEND_ORIGINS cannot contain '*' when credentialed auth cookies are enabled")

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

app = FastAPI(title="CropConnect ESP32 Ingestion API", version="1.0.0")


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["x-request-id"] = rid
    return response


@app.middleware("http")
async def add_security_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response


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

app.include_router(public_router.router)
app.include_router(auth_router.router)
app.include_router(sensors_router.router)
app.include_router(pumps_router.router)
app.include_router(farm_router.router)
app.include_router(market_router.router)
app.include_router(weather_router.router)
app.include_router(ai_router.router)


def create_app():
    return app
