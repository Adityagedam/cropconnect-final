# FastAPI dependency providers for settings and authenticated users.
from typing import Annotated

from fastapi import Cookie, Header

from config import Settings, settings
from services.auth_service import AUTH_COOKIE_NAME, require_auth_owner


def get_settings() -> Settings:
    return settings


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth_cookie: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> tuple[int, str]:
    return require_auth_owner(authorization, auth_cookie)
