import os
import time
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from mysql.connector import IntegrityError

os.environ.setdefault("CROP_DATA_SECRET_KEY", "test-data-secret-for-unit-tests")
os.environ.setdefault("CROP_AUTH_TOKEN_SECRET", "test-auth-secret-for-unit-tests")

import security_crypto as crypto  # noqa: E402
from app import app  # noqa: E402
from routers import auth as auth_routes  # noqa: E402
from routers import pumps as pump_routes  # noqa: E402
from services import rate_limit as rate_limit_service  # noqa: E402


class FakeCursor:
    def __init__(self, row=None, execute_error=None):
        self.row = row
        self.execute_error = execute_error
        self.lastrowid = 1
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, *_args, **_kwargs):
        if self.execute_error:
            raise self.execute_error

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        return None


class SecurityAndEndpointTests(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip_and_password_verification(self):
        encrypted = crypto.encrypt_text("secret phone")
        self.assertTrue(str(encrypted).startswith(crypto.ENCRYPTED_PREFIX))
        self.assertEqual(crypto.decrypt_text(encrypted), "secret phone")

        stored = crypto.hash_password("correct-password")
        self.assertTrue(crypto.verify_password("correct-password", stored))
        self.assertFalse(crypto.verify_password("wrong-password", stored))

    def test_auth_token_verifies_and_expires(self):
        token = crypto.sign_auth_token({"id": 7, "email": "farmer@example.com"}, ttl_seconds=1)
        self.assertEqual(crypto.verify_auth_token(token)["id"], 7)

        with patch("security_crypto.time.time", return_value=time.time() + 5):
            self.assertIsNone(crypto.verify_auth_token(token))

    def test_login_wrong_password_returns_401(self):
        client = TestClient(app)
        wrong_hash = crypto.hash_password("correct-password")
        fake_conn = FakeConnection(FakeCursor({"id": 1, "email": "farmer@example.com", "password": wrong_hash}))

        with patch.object(auth_routes, "rate_limit_public_request"), patch.object(auth_routes, "get_farmers_connection", return_value=fake_conn):
            response = client.post("/api/auth/login", json={"email": "farmer@example.com", "password": "wrong-password"})

        self.assertEqual(response.status_code, 401)

    def test_signup_duplicate_email_returns_409(self):
        client = TestClient(app)
        fake_conn = FakeConnection(FakeCursor(execute_error=IntegrityError("Duplicate entry for email")))
        payload = {
            "name": "Test Farmer",
            "email": "farmer@example.com",
            "password": "correct-password",
            "phone": "9999999999",
            "state": "Maharashtra",
            "location": "Pune",
            "land_size": 2,
        }

        with patch.object(auth_routes, "rate_limit_public_request"), patch.object(auth_routes, "get_farmers_connection", return_value=fake_conn):
            response = client.post("/api/auth/signup", json=payload)

        self.assertEqual(response.status_code, 409)

    def test_rate_limiter_raises_429_after_limit(self):
        original_fail_open = rate_limit_service.PUBLIC_RATE_LIMIT_DB_FAIL_OPEN
        rate_limit_service.PUBLIC_RATE_LIMIT_DB_FAIL_OPEN = True
        rate_limit_service.PUBLIC_RATE_LIMITS.clear()
        try:
            with patch.object(rate_limit_service, "get_connection", side_effect=RuntimeError("db unavailable")):
                rate_limit_service.rate_limit_named_key("unit-test", "client", limit=1, window_seconds=60)
                with self.assertRaises(HTTPException) as raised:
                    rate_limit_service.rate_limit_named_key("unit-test", "client", limit=1, window_seconds=60)
            self.assertEqual(raised.exception.status_code, 429)
        finally:
            rate_limit_service.PUBLIC_RATE_LIMIT_DB_FAIL_OPEN = original_fail_open
            rate_limit_service.PUBLIC_RATE_LIMITS.clear()

    def test_relay_parser_ignores_bad_keys_and_keeps_edge_relays(self):
        states = pump_routes.parse_relay_states({"relay1": "on", "r8": "1", "relay9": "on", "api_key": "secret", "bad": "on"})
        self.assertTrue(states[1])
        self.assertTrue(states[8])
        self.assertTrue(states[9])
        self.assertNotIn("bad", states)


if __name__ == "__main__":
    unittest.main()
