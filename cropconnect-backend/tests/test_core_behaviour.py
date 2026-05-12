import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError


os.environ.setdefault("CROP_DATA_SECRET_KEY", "test-data-secret-for-unit-tests")
os.environ.setdefault("CROP_AUTH_TOKEN_SECRET", "test-auth-secret-for-unit-tests")

import esp32_ingest as api  # noqa: E402
from crop_ai_agent import (  # noqa: E402
    build_crop_recommendation_messages,
    has_core_sensor_context,
    missing_crop_readings,
)


class BackendCoreBehaviourTests(unittest.TestCase):
    def test_email_validation_normalizes_and_rejects_bad_values(self):
        payload = api.AuthLoginIn(email=" Farmer@Example.COM ", password="strong-pass")
        self.assertEqual(payload.email, "farmer@example.com")

        with self.assertRaises(ValidationError):
            api.AuthLoginIn(email="not-an-email", password="strong-pass")

    def test_translation_payload_limits_are_enforced(self):
        valid = api.TranslateIn(texts=["Hello"], target_lang="hi")
        self.assertEqual(valid.texts, ["Hello"])

        with self.assertRaises(ValidationError):
            api.TranslateIn(texts=["x" * (api.TRANSLATION_TEXT_LIMIT + 1)], target_lang="hi")

        with self.assertRaises(ValidationError):
            api.TranslateIn(texts=["x"] * (api.TRANSLATION_BATCH_LIMIT + 1), target_lang="hi")

    def test_ai_json_parser_accepts_fenced_json_without_extra_text(self):
        self.assertEqual(api.parse_ai_json('```json\n{"crops":[],"summary":"ok"}\n```'), {"crops": [], "summary": "ok"})
        self.assertEqual(api.parse_ai_json('AI said: [{"name":"wheat"}] done'), [{"name": "wheat"}])

    def test_sensor_rows_drop_missing_values_without_turning_them_to_zero(self):
        row = {
            "device_id": "main-sim800l",
            "soil_moisture": Decimal("42.5"),
            "humidity": None,
            "temperature": Decimal("29.1"),
            "ph": Decimal("6.8"),
            "nitrogen": None,
            "phosphorus": None,
            "potassium": None,
            "recorded_at": datetime(2026, 5, 12, 8, 30, tzinfo=timezone.utc),
        }

        readings = api.reading_to_sensor_list(row)
        self.assertEqual([reading["sensor_type"] for reading in readings], ["soil_moisture", "temperature", "ph"])
        self.assertEqual(readings[0]["value"], 42.5)
        self.assertTrue(readings[0]["recorded_at"].startswith("2026-05-12T08:30:00"))

    def test_crop_ai_context_requires_live_core_readings(self):
        context = {
            "soil_moisture": 42,
            "humidity": 61,
            "temperature": 29,
            "ph": 6.7,
            "nitrogen": None,
            "phosphorus": None,
            "potassium": None,
        }

        self.assertTrue(has_core_sensor_context(context))
        self.assertEqual(missing_crop_readings(context), ["nitrogen", "phosphorus", "potassium"])

        no_ph_context = {**context, "ph": None}
        self.assertFalse(has_core_sensor_context(no_ph_context))

        messages = build_crop_recommendation_messages(context)
        self.assertIn("Never use hidden static crop tables", messages[0]["content"])
        self.assertIn('"soil_moisture": 42', messages[1]["content"])

    def test_weather_code_mapping_uses_unknown_marker_for_missing_data(self):
        self.assertEqual(api.weather_code_condition(61)["condition"], "Rain")
        self.assertEqual(api.weather_code_condition(None)["condition"], "--")

    def test_market_records_normalize_data_gov_price_rows(self):
        row = {
            "State": "Maharashtra",
            "District": "Pune",
            "Market": "Pune",
            "Commodity": "Tomato",
            "Variety": "Local",
            "Grade": "FAQ",
            "Arrival_Date": "13/05/2026",
            "Min_Price": "1200",
            "Max_Price": "1,800",
            "Modal_Price": "1500",
        }

        normalized = api.normalize_market_record(row)

        self.assertEqual(normalized["state"], "Maharashtra")
        self.assertEqual(normalized["district"], "Pune")
        self.assertEqual(normalized["commodity"], "Tomato")
        self.assertEqual(normalized["minPrice"], 1200)
        self.assertEqual(normalized["maxPrice"], 1800)
        self.assertEqual(normalized["modalPrice"], 1500)

    def test_market_payload_groups_mandi_records_without_fake_prices(self):
        payload = api.market_payload_from_records(
            [
                {
                    "state": "Maharashtra",
                    "district": "Pune",
                    "market": "Pune",
                    "commodity": "Tomato",
                    "modal_price": "1500",
                },
                {
                    "state": "Maharashtra",
                    "district": "Pune",
                    "market": "Pune",
                    "commodity": "Onion",
                    "modal_price": "",
                },
            ],
            requested_state="Maharashtra",
            requested_location="Pune, Maharashtra",
        )

        self.assertEqual(payload["recordsCount"], 1)
        self.assertEqual(payload["prices"][0]["modalPrice"], 1500)
        self.assertEqual(payload["mandis"][0]["commodities"][0]["commodity"], "Tomato")

    def test_market_ai_insight_payload_is_sanitized(self):
        payload = api.normalize_market_insight_payload(
            {
                "summary": "Hold if quality is good.",
                "recommendations": [
                    {
                        "title": "Compare nearby mandis",
                        "action": "Check the modal prices before selling.",
                        "reason": "Live records show more than one market.",
                        "confidence": "medium",
                    }
                ],
                "watch": ["Arrival date freshness"],
            }
        )

        self.assertEqual(payload["summary"], "Hold if quality is good.")
        self.assertEqual(payload["recommendations"][0]["confidence"], "medium")
        self.assertEqual(payload["watch"], ["Arrival date freshness"])

    def test_market_location_prefers_profile_district(self):
        state, district, requested_location = api.user_market_location(
            {
                "state": "Maharashtra",
                "district": "Pune",
                "city": "Baramati",
                "locationType": "city",
            }
        )

        self.assertEqual(state, "Maharashtra")
        self.assertEqual(district, "Pune")
        self.assertEqual(requested_location, "Baramati, Pune, Maharashtra")


if __name__ == "__main__":
    unittest.main()
