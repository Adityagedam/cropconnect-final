import json

from fastapi import APIRouter, Cookie, Header, HTTPException, Request

from config import settings
from crop_ai_agent import build_crop_recommendation_messages, has_core_sensor_context, missing_crop_readings
from logging_config import configure_logging
from models import AIOrchestrateIn, ChatIn, CropRecommendIn, TranslateIn
from services.ai_service import (
    LANGUAGE_NAMES,
    ai_model_name,
    ai_provider,
    chat_completion_text,
    classify_farm_scope_with_ai,
    google_search,
    is_market_question,
    parse_ai_json,
    require_ai_provider,
    selected_language,
    translate_texts_with_ai,
)
from services.auth_service import insert_chat_record, owner_profile_context, require_auth_owner
from services.market_service import live_market_context_for_profile
from services.rate_limit import rate_limit_authenticated_request, rate_limit_public_request
from services.sensor_service import latest_sensor_context

AUTH_COOKIE_NAME = "cropconnect_auth"
PUBLIC_TRANSLATION_ENABLED = settings.public_translation_enabled
router = APIRouter()
logger = configure_logging()


def raise_public_error(status_code: int, detail: str, context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)
    raise HTTPException(status_code=status_code, detail=detail) from exc


def fallback_farm_reply(message: str, live_sensor_context: dict, profile_location: str) -> str:
    sensor_data = live_sensor_context.get("sensor_data") or {}
    soil_moisture = sensor_data.get("soil_moisture")
    temperature = sensor_data.get("temperature")
    humidity = sensor_data.get("humidity")
    sensor_message = live_sensor_context.get("message") or ""
    location_text = f" for {profile_location}" if profile_location else ""
    readings = []
    if soil_moisture is not None:
        readings.append(f"soil moisture is {soil_moisture}")
    if temperature is not None:
        readings.append(f"temperature is {temperature}")
    if humidity is not None:
        readings.append(f"humidity is {humidity}")
    reading_text = ", ".join(readings)
    context_text = f" Your latest readings show {reading_text}." if reading_text else f" {sensor_message or 'Live sensor readings are not available yet.'}"
    return (
        "I can help with this farm question, but the cloud AI model is temporarily unavailable."
        + context_text
        + f" For irrigation{location_text}, check the latest soil moisture before switching pumps on, avoid watering during peak afternoon heat, and recheck the field after a short run."
        + " If the soil is already moist or rain is expected, delay irrigation and keep monitoring the ESP32 readings."
        + f" Your question was: {message}"
    )


@router.post("/api/utils/translate")
async def api_translate(payload: TranslateIn, request: Request):
    if not PUBLIC_TRANSLATION_ENABLED:
        raise HTTPException(status_code=503, detail="Public translation endpoint is disabled")
    rate_limit_public_request(request, "translate", limit=30, window_seconds=60)
    texts = payload.texts or ([payload.text] if payload.text else [])
    texts = [text for text in texts if text is not None]
    if not texts:
        raise HTTPException(status_code=422, detail="Provide text or texts to translate")

    translated = translate_texts_with_ai(texts, payload.target_lang)
    response = {
        "ok": True,
        "target_lang": payload.target_lang,
        "translations": translated,
    }
    if payload.text is not None and payload.texts is None:
        response["translated"] = translated[0]
    return response


@router.post("/api/ai/chat")
def ai_chat(
    payload: ChatIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-chat", limit=20, window_seconds=60)
    related_to_plant_or_soil = classify_farm_scope_with_ai(payload.message, payload.language)
    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    live_sensor_context = latest_sensor_context(device_id)
    live_sensor_data = live_sensor_context.get("sensor_data") or {}
    profile_location = ", ".join(
        item
        for item in [
            owner_profile.get("village") or owner_profile.get("city") or owner_profile.get("location"),
            owner_profile.get("district"),
            owner_profile.get("state"),
        ]
        if item
    )
    live_market_data = live_market_context_for_profile(owner_profile) if is_market_question(payload.message) else {}

    if not related_to_plant_or_soil:
        reply = (
            "I can only help with farm, crop, soil, irrigation, sensor, weather, pest, fertilizer, pump, "
            "or mandi topics. Ask me something like: which crop fits my latest soil readings?"
        )
        insert_chat_record(owner_id, owner_email, "user", payload.message, False, live_sensor_data, profile_location)
        insert_chat_record(owner_id, owner_email, "bot", reply, False, live_sensor_data, profile_location)
        return {
            "ok": True,
            "source": "scope_filter",
            "reply": reply,
            "related_to_plant_or_soil": False,
            "used_sensor_data": live_sensor_data,
            "sensor_source": live_sensor_context.get("source"),
            "sensor_recorded_at": live_sensor_context.get("recorded_at"),
            "sensor_message": live_sensor_context.get("message", ""),
            "used_google_search": False,
        }

    context = {
        "location": profile_location,
        "language": payload.language,
        "account": {
            "id": owner_id,
            "email": owner_email,
            "name": owner_profile.get("name") or "",
            "state": owner_profile.get("state") or "",
            "district": owner_profile.get("district") or "",
            "city": owner_profile.get("city") or "",
            "village": owner_profile.get("village") or "",
            "land_size": owner_profile.get("landSize"),
        },
        "live_sensor_context": live_sensor_context,
        "dashboard_sensor_data": {},
        "market_data": live_market_data,
        "weather_data": {},
    }
    search_results = google_search(payload.message, profile_location) if related_to_plant_or_soil else []

    if ai_provider() == "openai" and not settings.openai_api_key:
        fallback_reply = fallback_farm_reply(payload.message, live_sensor_context, profile_location)
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        insert_chat_record(owner_id, owner_email, "bot", fallback_reply, related_to_plant_or_soil, live_sensor_data, profile_location)
        return {
            "ok": True,
            "source": "local_fallback",
            "related_to_plant_or_soil": related_to_plant_or_soil,
            "reply": fallback_reply,
            "sensor_source": live_sensor_context.get("source"),
            "sensor_recorded_at": live_sensor_context.get("recorded_at"),
            "sensor_message": live_sensor_context.get("message", ""),
            "used_google_search": bool(search_results),
        }
    if ai_provider() == "gemini" and not settings.gemini_api_key:
        fallback_reply = fallback_farm_reply(payload.message, live_sensor_context, profile_location)
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        insert_chat_record(owner_id, owner_email, "bot", fallback_reply, related_to_plant_or_soil, live_sensor_data, profile_location)
        return {
            "ok": True,
            "source": "local_fallback",
            "related_to_plant_or_soil": related_to_plant_or_soil,
            "reply": fallback_reply,
            "sensor_source": live_sensor_context.get("source"),
            "sensor_recorded_at": live_sensor_context.get("recorded_at"),
            "sensor_message": live_sensor_context.get("message", ""),
            "used_google_search": bool(search_results),
        }

    messages = [
        {
            "role": "developer",
            "content": (
                "You are CropConnect's farming assistant for an IoT farming dashboard. "
                "Your scope is crops, soil, irrigation, sensors, weather, pests/diseases, fertilizer, pumps, and market/mandi decisions. "
                "Never answer questions outside that farming scope. For unrelated questions, briefly say you can only help with farm, crop, soil, irrigation, sensor, weather, pest, fertilizer, pump, or mandi topics, then offer one farming question the user can ask. "
                "Always answer the latest user question directly; never repeat or continue an older answer unless the latest question clearly asks for a follow-up. "
                "Give concise, practical guidance with simple language, short paragraphs, and clear next steps. "
                "Prefer 2-5 actionable points over long explanations. Use live_sensor_context as the primary source for sensor readings because it is loaded from the latest MySQL ESP32 row. Use dashboard_sensor_data only as secondary context. "
                "Treat null, missing, empty, unavailable, or -- sensor values as unknown, never as zero. If live sensor data is unavailable, say that and explain what reading is needed. "
                "Use market_data for mandi questions only when recordsCount is greater than 0. If market_data is empty or unavailable, say live mandi prices are unavailable instead of guessing. "
                "Do not invent sensor readings, market prices, weather facts, crop disease certainty, or chemical dosages. "
                "If a question needs certified agronomy, veterinary, legal, medical, or financial advice, say so clearly. "
                "When web search results are supplied, use them as supporting context and mention that the "
                "answer is based on the available search snippets, not direct Google pages. "
                "Always answer in the user's selected language (" + LANGUAGE_NAMES.get(selected_language(payload), payload.language) + ") only. "
                "If the user's spoken or typed message is in another language, understand it, "
                "but reply only in the selected language, not in the input language."
            ),
        },
        {"role": "user", "content": "Current CropConnect dashboard context: " + json.dumps(context, ensure_ascii=False, default=str)},
    ]
    if search_results:
        messages.append(
            {
                "role": "user",
                "content": "Google search context: " + str(search_results),
            }
        )
    if payload.history:
        messages.append(
            {
                "role": "user",
                "content": "Earlier chat history below is context only. Do not answer it unless the latest question asks for a follow-up.",
            }
        )
    for item in payload.history[-4:]:
        role = "assistant" if item.get("type") == "bot" else "user"
        text = item.get("text", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({
        "role": "user",
        "content": (
            "Answer this latest question only. Desired reply language: "
            + LANGUAGE_NAMES.get(selected_language(payload), payload.language)
            + ". Input language: "
            + payload.input_language
            + ". Latest question: "
            + payload.message
        ),
    })

    try:
        reply = chat_completion_text(messages, temperature=0.25, max_tokens=600)
    except Exception as exc:
        logger.exception("AI chatbot request failed, using local fallback: %s", exc)
        fallback_reply = fallback_farm_reply(payload.message, live_sensor_context, profile_location)
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        insert_chat_record(owner_id, owner_email, "bot", fallback_reply, related_to_plant_or_soil, live_sensor_data, profile_location)
        return {
            "ok": True,
            "source": "local_fallback",
            "related_to_plant_or_soil": related_to_plant_or_soil,
            "reply": fallback_reply,
            "sensor_source": live_sensor_context.get("source"),
            "sensor_recorded_at": live_sensor_context.get("recorded_at"),
            "sensor_message": live_sensor_context.get("message", ""),
            "used_google_search": bool(search_results),
        }

    if not reply:
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        raise HTTPException(status_code=502, detail="AI chatbot returned an empty answer")

    final_reply = reply
    insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
    insert_chat_record(owner_id, owner_email, "bot", final_reply, related_to_plant_or_soil, live_sensor_data, profile_location)
    return {
        "ok": True,
        "related_to_plant_or_soil": related_to_plant_or_soil,
        "reply": final_reply,
        "sensor_source": live_sensor_context.get("source"),
        "sensor_recorded_at": live_sensor_context.get("recorded_at"),
        "sensor_message": live_sensor_context.get("message", ""),
        "used_google_search": bool(search_results),
    }


@router.post("/api/crops/recommend")
def crop_recommend(
    payload: CropRecommendIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-crop-recommend", limit=8, window_seconds=15 * 60)
    require_ai_provider()

    owner_profile = owner_profile_context(owner_id)
    owner_device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    requested_device_id = str(payload.device_id or "").strip()
    if not owner_device_id:
        raise HTTPException(status_code=400, detail="No sensor device is configured for this account")
    if requested_device_id and requested_device_id != owner_device_id:
        raise HTTPException(status_code=403, detail="Sensor device does not belong to this account")

    device_id = owner_device_id
    live_sensor_context = latest_sensor_context(device_id)
    live_sensor_data = live_sensor_context.get("sensor_data") or {}
    profile_location = ", ".join(
        item
        for item in [
            owner_profile.get("village") or owner_profile.get("city") or owner_profile.get("location"),
            owner_profile.get("district"),
            owner_profile.get("state"),
        ]
        if item
    )
    context = {
        "soil_moisture": live_sensor_data.get("soil_moisture"),
        "humidity": live_sensor_data.get("humidity"),
        "temperature": live_sensor_data.get("temperature"),
        "ph": live_sensor_data.get("ph"),
        "nitrogen": live_sensor_data.get("nitrogen"),
        "phosphorus": live_sensor_data.get("phosphorus"),
        "potassium": live_sensor_data.get("potassium"),
        "goal": payload.goal,
        "location": profile_location,
        "acreage": owner_profile.get("landSize"),
        "season": payload.season,
        "language": payload.language,
        "device_id": device_id,
        "sensor_source": live_sensor_context.get("source"),
        "sensor_recorded_at": live_sensor_context.get("recorded_at"),
        "sensor_message": live_sensor_context.get("message"),
    }
    missing_readings = missing_crop_readings(context)
    if not has_core_sensor_context(context):
        return {
            "ok": True,
            "source": "no_live_sensor_data",
            "model": None,
            "crops": [],
            "summary": "",
            "missing_readings": missing_readings,
            "sensor_context": live_sensor_context,
        }

    try:
        raw = chat_completion_text(build_crop_recommendation_messages(context), temperature=0.2, max_tokens=1200)
        parsed = parse_ai_json(raw)
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "AI crop recommendation failed", "AI crop recommendation request failed", exc)

    crops = parsed.get("crops") if isinstance(parsed, dict) else None
    if not isinstance(crops, list):
        raise HTTPException(status_code=502, detail="AI crop recommendation returned invalid data")

    return {
        "ok": True,
        "source": ai_provider(),
        "model": ai_model_name(),
        "crops": crops,
        "summary": parsed.get("summary", "") if isinstance(parsed, dict) else "",
        "missing_readings": missing_readings,
        "sensor_context": live_sensor_context,
    }


@router.post("/api/ai/orchestrate")
def ai_orchestrate(
    payload: AIOrchestrateIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-orchestrate", limit=8, window_seconds=15 * 60)
    require_ai_provider()

    owner_profile = owner_profile_context(owner_id)
    device_id = str(owner_profile.get("sensorDeviceId") or "").strip()
    context = {
        "objective": payload.objective,
        "language": payload.language,
        "account": {
            "id": owner_id,
            "email": owner_email,
            "name": owner_profile.get("name") or "",
            "state": owner_profile.get("state") or "",
            "district": owner_profile.get("district") or "",
            "city": owner_profile.get("city") or "",
            "village": owner_profile.get("village") or "",
            "land_size": owner_profile.get("landSize"),
            "sensor_device_id": device_id,
        },
        "live_sensor_context": latest_sensor_context(device_id),
    }
    prompt = (
        "You are CropConnect's farm operations orchestrator. Analyze live sensor data, pump state, timers, "
        "weather, market context, and farmer objective. Return strict JSON only. "
        "Never directly actuate pumps or hardware. Any pump or irrigation change must be an action with "
        "\"requires_confirmation\": true. Keep advice practical and safety-first. "
        "JSON shape: {\"summary\":\"...\",\"risk_level\":\"low/medium/high\","
        "\"insights\":[\"...\"],\"actions\":[{\"id\":\"short-id\",\"title\":\"...\","
        "\"type\":\"pump|timer|crop|market|sensor|profile\",\"priority\":\"low/medium/high\","
        "\"requires_confirmation\":true,\"payload\":{},\"reason\":\"...\"}],"
        "\"questions\":[\"...\"]}."
    )

    try:
        raw = chat_completion_text(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
            ],
            temperature=0.15,
            max_tokens=1200,
        )
        parsed = parse_ai_json(raw)
    except HTTPException:
        raise
    except Exception as exc:
        raise_public_error(502, "AI orchestration failed", "AI orchestration request failed", exc)

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="AI orchestration returned invalid data")

    for action in parsed.get("actions", []) if isinstance(parsed.get("actions"), list) else []:
        if isinstance(action, dict) and action.get("type") in {"pump", "timer"}:
            action["requires_confirmation"] = True

    return {
        "ok": True,
        "source": ai_provider(),
        "model": ai_model_name(),
        "plan": parsed,
    }
