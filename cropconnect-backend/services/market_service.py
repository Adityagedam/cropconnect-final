# Market data normalization and live mandi context helpers.
import json
import re
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from config import settings
from http_client import request_json
from logging_config import configure_logging
from services.ai_service import selected_language_name

logger = configure_logging()


def log_backend_error(context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)


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
        "sourceUrl": settings.data_gov_market_resource_url,
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
        "api-key": settings.data_gov_api_key,
        "format": "json",
        "limit": str(settings.market_price_limit),
        "offset": "0",
        "filters[State]": state,
    }
    if district:
        params["filters[District]"] = district
    if commodity:
        params["filters[Commodity]"] = commodity

    url = f"{settings.data_gov_market_resource_url}?{urllib.parse.urlencode(params)}"
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
    if not settings.data_gov_api_key:
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
