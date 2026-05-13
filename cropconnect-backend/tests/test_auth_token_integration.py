# Integration coverage for signed auth token lifecycle behavior.
import time
import unittest
from unittest.mock import patch

from security_crypto import refresh_auth_token, sign_auth_token, verify_auth_token


class AuthTokenIntegrationTests(unittest.TestCase):
    def test_auth_token_round_trips(self):
        token = sign_auth_token({"id": 1, "email": "farmer@example.com"})
        payload = verify_auth_token(token)

        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["email"], "farmer@example.com")

    def test_expired_auth_token_returns_none(self):
        token = sign_auth_token({"id": 1}, ttl_seconds=1)
        with patch("security_crypto.time.time", return_value=time.time() + 5):
            self.assertIsNone(verify_auth_token(token))

    def test_tampered_auth_token_returns_none(self):
        token = sign_auth_token({"id": 1})
        prefix, body, signature = token.rsplit(".", 2)

        self.assertIsNone(verify_auth_token(f"{prefix}.{body}.tampered"))
        self.assertIsNone(verify_auth_token(f"{prefix}.tampered.{signature}"))

    def test_refresh_auth_token_only_when_expiring_soon(self):
        token = sign_auth_token({"id": 1, "email": "farmer@example.com"}, ttl_seconds=60)
        refreshed = refresh_auth_token(token)

        self.assertTrue(refreshed)
        self.assertEqual(verify_auth_token(refreshed)["email"], "farmer@example.com")
        self.assertIsNone(refresh_auth_token(sign_auth_token({"id": 1})))


if __name__ == "__main__":
    unittest.main()
