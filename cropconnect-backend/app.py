# FastAPI application entrypoint and application-level middleware.
from fastapi import Request

from esp32_ingest import app


@app.middleware("http")
async def add_security_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def create_app():
    return app
