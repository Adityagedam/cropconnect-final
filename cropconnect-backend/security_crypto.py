import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

ENCRYPTED_PREFIX = "enc:v1:"
PASSWORD_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 210_000
AUTH_TOKEN_PREFIX = "ccauth.v1"
AUTH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


def _secret() -> str:
    return os.getenv("CROP_DATA_SECRET_KEY") or ""


def _auth_secret() -> str:
    return os.getenv("CROP_AUTH_TOKEN_SECRET") or ""


def require_data_secret() -> None:
    if not _secret():
        raise RuntimeError("CROP_DATA_SECRET_KEY is required before starting CropConnect backend")
    if not _auth_secret():
        raise RuntimeError("CROP_AUTH_TOKEN_SECRET is required before starting CropConnect backend")


def _fernet() -> Fernet:
    secret = _secret()
    if not secret:
        raise RuntimeError("CROP_DATA_SECRET_KEY is required for encrypted values")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_text(value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if not text or text.startswith(ENCRYPTED_PREFIX):
        return text
    token = _fernet().encrypt(text.encode("utf-8")).decode("utf-8")
    return ENCRYPTED_PREFIX + token


def decrypt_text(value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if not text.startswith(ENCRYPTED_PREFIX):
        return text
    token = text[len(ENCRYPTED_PREFIX):]
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Encrypted database value cannot be decrypted with the configured CROP_DATA_SECRET_KEY") from exc


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"{PASSWORD_PREFIX}${PBKDF2_ITERATIONS}${salt}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if not stored.startswith(PASSWORD_PREFIX + "$"):
        return False

    try:
        _, iterations, salt, expected = stored.split("$", 3)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        actual = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_auth_token(payload: dict[str, Any], ttl_seconds: int = AUTH_TOKEN_TTL_SECONDS) -> str:
    secret = _auth_secret()
    if not secret:
        raise RuntimeError("CROP_AUTH_TOKEN_SECRET or CROP_DATA_SECRET_KEY is required for auth tokens")

    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + ttl_seconds}
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_token = _b64url_encode(body_bytes)
    signature = hmac.new(secret.encode("utf-8"), body_token.encode("ascii"), hashlib.sha256).digest()
    return f"{AUTH_TOKEN_PREFIX}.{body_token}.{_b64url_encode(signature)}"


def verify_auth_token(token: str) -> dict[str, Any] | None:
    secret = _auth_secret()
    if not secret or not token:
        return None

    try:
        prefix_part, version_part, body_token, signature_token = token.split(".", 3)
        prefix = f"{prefix_part}.{version_part}"
        if prefix != AUTH_TOKEN_PREFIX:
            return None
        expected = hmac.new(secret.encode("utf-8"), body_token.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(signature_token)
        if not hmac.compare_digest(actual, expected):
            return None
        payload = json.loads(_b64url_decode(body_token).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None
