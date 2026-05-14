# Market price and AI market insight routes.
from fastapi import APIRouter, Cookie, Header, HTTPException, Query

from config import settings
from logging_config import configure_logging
from models import MarketInsightIn
from services.ai_service import ai_model_name, ai_provider, chat_completion_text, parse_ai_json, require_ai_provider
from services.auth_service import owner_profile_context, require_auth_owner
from services.market_service import (
    build_market_insight_messages,
    data_gov_market_records,
    live_market_context_for_profile,
    market_payload_from_records,
    market_text,
    normalize_market_insight_payload,
    user_market_location,
)
from services.rate_limit import rate_limit_authenticated_request
from services.sensor_service import latest_sensor_context

AUTH_COOKIE_NAME = "cropconnect_auth"
router = APIRouter()
logger = configure_logging()


def raise_public_error(status_code: int, detail: str, context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/api/market/prices")
def market_prices(
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    commodity: str = Query(default="", max_length=80),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "market-prices", limit=20, window_seconds=60)

    if not settings.data_gov_api_key:
        raise HTTPException(status_code=503, detail="Live mandi price feed is not configured")

    profile = owner_profile_context(owner_id)
    state, district_candidate, requested_location = user_market_location(profile)
    if not state:
        raise HTTPException(status_code=400, detail="Add your state in profile to load local mandi prices")

    requested_commodity = market_text(commodity)
    matched_district = ""
    message = ""
    try:
        records = []
        if district_candidate:
            records = data_gov_market_records(state, district_candidate, requested_commodity)
            matched_district = district_candidate if records else ""
        if not records:
            records = data_gov_market_records(state, "", requested_commodity)
            if district_candidate and records:
                message = (
                    f"No district-level mandi records found for {district_candidate}; "
                    "showing latest state-level records."
                )
    except Exception as exc:
        logger.exception("Data.gov mandi request failed, returning empty market payload: %s", exc)
        return market_payload_from_records(
            [],
            state,
            requested_location,
            "",
            "Live mandi feed is currently unavailable.",
        )

    return market_payload_from_records(records, state, requested_location, matched_district, message)


@router.post("/api/market/insights")
def market_insights(
    payload: MarketInsightIn,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-market-insights", limit=6, window_seconds=15 * 60)
    require_ai_provider()

    if not settings.data_gov_api_key:
        raise HTTPException(status_code=503, detail="Live mandi price feed is not configured")

    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    market_context = live_market_context_for_profile(owner_profile)
    live_sensor_context = latest_sensor_context(device_id) if device_id else {
        "source": "unavailable",
        "sensor_data": {},
        "message": "No sensor device is configured for this account.",
    }

    if not market_context.get("recordsCount"):
        return {
            "ok": True,
            "source": "no_live_market_data",
            "model": None,
            "summary": market_context.get("message") or "Live mandi prices are unavailable for this location.",
            "recommendations": [],
            "watch": [],
            "market_data": market_context,
            "sensor_context": live_sensor_context,
        }

    context = {
        "account": {
            "state": owner_profile.get("state") or "",
            "district": owner_profile.get("district") or "",
            "city": owner_profile.get("city") or "",
            "village": owner_profile.get("village") or "",
            "land_size": owner_profile.get("landSize"),
        },
        "market_data": market_context,
        "live_sensor_context": live_sensor_context,
    }

    try:
        raw = chat_completion_text(
            build_market_insight_messages(context, payload.language, payload.objective),
            temperature=0.2,
            max_tokens=800,
        )
        insight = normalize_market_insight_payload(parse_ai_json(raw))
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "AI market insight failed", "AI market insight request failed", exc)

    return {
        "ok": True,
        "source": f"{ai_provider()}_with_live_market_data",
        "model": ai_model_name(),
        **insight,
        "market_data": market_context,
        "sensor_context": live_sensor_context,
    }
