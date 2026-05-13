# ruff: noqa: F821
from __future__ import annotations

from typing import get_type_hints

from fastapi import APIRouter, Cookie, Header, HTTPException, Request

AUTH_COOKIE_NAME = "cropconnect_auth"

_core = None


def _resolve_route_types(*functions):
    for func in functions:
        func.__annotations__ = get_type_hints(func, globalns=globals(), localns=globals())


def _bind_core(core):
    global _core
    _core = core
    for name in dir(core):
        if not name.startswith("__"):
            globals()[name] = getattr(core, name)


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


def ai_chat(
    payload: ChatIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-chat", limit=20, window_seconds=60)
    try:
        related_to_plant_or_soil = classify_farm_scope_with_ai(payload.message, payload.language)
    except Exception as exc:
        raise_public_error(502, "AI scope check failed", "AI chat scope classifier failed", exc)
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

    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for AI chatbot answers")

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
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": messages,
                "temperature": 0.25,
                "max_tokens": 600,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
    except Exception as exc:
        insert_chat_record(owner_id, owner_email, "user", payload.message, related_to_plant_or_soil, live_sensor_data, profile_location)
        raise_public_error(502, "AI chatbot request failed", "AI chatbot request failed", exc)

    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
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


def crop_recommend(
    payload: CropRecommendIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, _owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-crop-recommend", limit=8, window_seconds=15 * 60)
    require_openai()

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
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": build_crop_recommendation_messages(context),
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
        "source": "openai",
        "model": OPENAI_MODEL,
        "crops": crops,
        "summary": parsed.get("summary", "") if isinstance(parsed, dict) else "",
        "missing_readings": missing_readings,
        "sensor_context": live_sensor_context,
    }


def ai_orchestrate(
    payload: AIOrchestrateIn,
    request: Request,
    authorization: str | None = Header(default=None),
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
):
    owner_id, owner_email = require_auth_owner(authorization, auth_cookie)
    rate_limit_authenticated_request(owner_id, "ai-orchestrate", limit=8, window_seconds=15 * 60)
    require_openai()

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
        data = request_json(
            "https://api.openai.com/v1/chat/completions",
            {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
                ],
                "temperature": 0.15,
                "max_tokens": 1200,
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
        "source": "openai",
        "model": OPENAI_MODEL,
        "plan": parsed,
    }


def create_router(core) -> APIRouter:
    _bind_core(core)
    _resolve_route_types(api_translate, ai_chat, crop_recommend, ai_orchestrate)
    router = APIRouter()
    router.add_api_route('/api/utils/translate', api_translate, methods=['POST'])
    router.add_api_route('/api/ai/chat', ai_chat, methods=['POST'])
    router.add_api_route('/api/crops/recommend', crop_recommend, methods=['POST'])
    router.add_api_route('/api/ai/orchestrate', ai_orchestrate, methods=['POST'])
    return router
