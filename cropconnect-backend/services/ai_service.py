# AI classification, translation, parsing, and web-search helpers.
import json
import urllib.parse
from collections import OrderedDict
from typing import Any

from fastapi import HTTPException

from config import settings
from http_client import request_json
from logging_config import configure_logging

logger = configure_logging()

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
    "te": "Telugu",
    "ta": "Tamil",
    "bn": "Bengali",
    "kn": "Kannada",
}

PLANT_SOIL_TERMS = {
    "agriculture",
    "agronomy",
    "crop",
    "crops",
    "farm",
    "farming",
    "field",
    "plant",
    "plants",
    "seed",
    "seedling",
    "germination",
    "leaf",
    "leaves",
    "root",
    "roots",
    "stem",
    "flower",
    "fruit",
    "vegetable",
    "grain",
    "wheat",
    "rice",
    "maize",
    "corn",
    "soybean",
    "onion",
    "cotton",
    "sugarcane",
    "turmeric",
    "chilli",
    "groundnut",
    "soil",
    "moisture",
    "ph",
    "npk",
    "nitrogen",
    "phosphorus",
    "potassium",
    "fertilizer",
    "fertiliser",
    "compost",
    "manure",
    "irrigation",
    "irrigate",
    "water",
    "watering",
    "drip",
    "pest",
    "disease",
    "fungus",
    "fungal",
    "weed",
    "harvest",
    "sowing",
    "spray",
    "pesticide",
    "weather",
    "rain",
    "humidity",
    "temperature",
    "sensor",
    "sensors",
    "pani",
    "paani",
    "sinchai",
    "kheti",
    "khet",
    "mitti",
    "mati",
    "fasal",
    "khad",
    "khaad",
    "mausam",
    "barish",
    "baarish",
    "mandi",
    "bhav",
    "bazar",
}

MARKET_QUESTION_TERMS = {
    "market",
    "mandi",
    "price",
    "prices",
    "rate",
    "rates",
    "sell",
    "selling",
    "buyer",
    "buyers",
    "msp",
    "bhav",
    "bazar",
    "bazaar",
    "commodity",
}

MULTILINGUAL_PLANT_SOIL_TERMS = {
    "खेती",
    "फसल",
    "मिट्टी",
    "सिंचाई",
    "पानी",
    "మట్టి",
    "பயிர்",
}

TRANSLATION_CACHE_MAX_ITEMS = 1000
TRANSLATION_CACHE: OrderedDict[str, str] = OrderedDict()


def raise_public_error(status_code: int, detail: str, context: str, exc: Exception) -> None:
    logger.exception("%s: %s", context, exc)
    raise HTTPException(status_code=status_code, detail=detail) from exc


def parse_ai_json(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start_candidates = [index for index in (cleaned.find("{"), cleaned.find("[")) if index != -1]
    if start_candidates:
        cleaned = cleaned[min(start_candidates):]
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end != -1:
        cleaned = cleaned[: end + 1]
    return json.loads(cleaned)


def require_openai() -> None:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required for AI-powered decisions")


def google_search(query: str, location: str | None = "") -> list[dict[str, str]]:
    if not settings.google_api_key or not settings.google_cse_id:
        return []

    search_query = f"{query} {location or ''} agriculture farming India".strip()
    url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode(
        {
            "key": settings.google_api_key,
            "cx": settings.google_cse_id,
            "q": search_query,
            "num": 5,
        }
    )
    try:
        data = request_json(url)
    except Exception as exc:
        logger.exception("google_search failed: %s", exc)
        return []

    return [
        {
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "link": item.get("link", ""),
        }
        for item in data.get("items", [])
    ]


def is_plant_or_soil_question(message: str) -> bool:
    normalized = message.lower().replace("-", " ")
    words = {word.strip(".,?!:;()[]{}\"'") for word in normalized.split()}

    if words & PLANT_SOIL_TERMS:
        return True
    if any(term in normalized for term in PLANT_SOIL_TERMS if len(term) > 4):
        return True
    return any(term in normalized for term in MULTILINGUAL_PLANT_SOIL_TERMS)


def is_market_question(message: str) -> bool:
    normalized = message.lower().replace("-", " ")
    words = {word.strip(".,?!:;()[]{}\"'") for word in normalized.split()}
    return bool(words & MARKET_QUESTION_TERMS) or any(term in normalized for term in MARKET_QUESTION_TERMS if len(term) > 4)


def selected_language(payload: Any) -> str:
    code = (payload.language or "en").lower().split("-", 1)[0]
    return code if code in LANGUAGE_NAMES else "en"


def selected_language_name(language: str | None) -> str:
    code = (language or "en").lower().split("-", 1)[0]
    return LANGUAGE_NAMES.get(code, LANGUAGE_NAMES["en"])


def classify_farm_scope_with_ai(message: str, language: str = "en") -> bool:
    if not settings.openai_api_key:
        return is_plant_or_soil_question(message)

    prompt = (
        "Classify whether the latest user message is asking for help about agriculture, farming, crops, soil, "
        "irrigation, farm sensors, pumps, farm weather, pests, fertilizer, or mandi/market decisions. "
        "Return {\"in_scope\":true} only when the actual request is about those farm topics. "
        "Return {\"in_scope\":false} for general knowledge, coding, entertainment, politics, adult content, "
        "medical/legal/financial advice not tied to farming, or messages that merely mention a farm word as a trick. "
        "Return strict JSON only."
    )
    data = request_json(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"message": message, "selected_language": language},
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 40,
        },
        {"Authorization": f"Bearer {settings.openai_api_key}"},
    )
    raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = parse_ai_json(raw)
    if not isinstance(parsed, dict) or "in_scope" not in parsed:
        raise ValueError("Scope classifier returned an unexpected response")
    return bool(parsed.get("in_scope"))


def translate_texts_with_ai(texts: list[str], target_lang: str) -> list[str]:
    target = target_lang.lower().strip()
    if target in ("en", "english"):
        return texts

    def cache_key(text: str) -> str:
        return f"{target}:{text}"

    def cached_value(text: str) -> str | None:
        key = cache_key(text)
        if key not in TRANSLATION_CACHE:
            return None
        TRANSLATION_CACHE.move_to_end(key)
        return TRANSLATION_CACHE[key]

    def remember_translation(source: str, translated: str) -> None:
        key = cache_key(source)
        TRANSLATION_CACHE[key] = translated
        TRANSLATION_CACHE.move_to_end(key)
        while len(TRANSLATION_CACHE) > TRANSLATION_CACHE_MAX_ITEMS:
            TRANSLATION_CACHE.popitem(last=False)

    missing = [text for text in texts if text and cached_value(text) is None]

    if missing:
        if not settings.openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")

        prompt = (
            "Translate this JSON array of CropConnect farming website UI strings from English "
            f"to {target_lang}. Preserve placeholders like {{name}}, {{moisture}}, {{temp}}, HTML tags, "
            "numbers, punctuation, and product names. Return only a JSON array of translated strings "
            "in the same order, with no explanation.\n\n"
            + json.dumps(missing, ensure_ascii=False)
        )

        try:
            response = request_json(
                "https://api.openai.com/v1/chat/completions",
                payload={
                    "model": settings.openai_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a precise UI localization engine. Output valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                },
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            raw = response["choices"][0]["message"]["content"].strip()
            translated_items = json.loads(raw)
            if not isinstance(translated_items, list) or len(translated_items) != len(missing):
                raise ValueError("Translator returned an unexpected response shape")

            for source, translated in zip(missing, translated_items, strict=False):
                remember_translation(source, str(translated))
        except HTTPException:
            raise
        except Exception as exc:
            raise_public_error(502, "Translation failed", "Translation request failed", exc)

    return [cached_value(text) or text for text in texts]
