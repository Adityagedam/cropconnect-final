# Integration coverage for public AI utility routes.
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from routers import ai as ai_routes


class AiRouterIntegrationTests(unittest.TestCase):
    def test_translate_returns_translated_text(self):
        client = TestClient(app)
        with (
            patch.object(ai_routes, "PUBLIC_TRANSLATION_ENABLED", True),
            patch.object(ai_routes, "rate_limit_public_request"),
            patch.object(ai_routes, "translate_texts_with_ai", return_value=["नमस्ते"]),
        ):
            response = client.post("/api/utils/translate", json={"text": "Hello", "target_lang": "hi"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["translations"], ["नमस्ते"])
        self.assertEqual(payload["translated"], "नमस्ते")

    def test_translate_rejects_empty_payload(self):
        client = TestClient(app)
        with patch.object(ai_routes, "PUBLIC_TRANSLATION_ENABLED", True), patch.object(ai_routes, "rate_limit_public_request"):
            response = client.post("/api/utils/translate", json={"target_lang": "hi"})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
