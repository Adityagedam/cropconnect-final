import json
from typing import Any

CORE_READING_FIELDS = ("soil_moisture", "humidity", "temperature", "ph")
OPTIONAL_READING_FIELDS = ("nitrogen", "phosphorus", "potassium")


def missing_crop_readings(context: dict[str, Any]) -> list[str]:
    missing = []
    for field in (*CORE_READING_FIELDS, *OPTIONAL_READING_FIELDS):
        if context.get(field) is None:
            missing.append(field)
    return missing


def has_core_sensor_context(context: dict[str, Any]) -> bool:
    return all(context.get(field) is not None for field in CORE_READING_FIELDS)


def build_crop_recommendation_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    missing = missing_crop_readings(context)
    context_with_missing = {
        **context,
        "missing_readings": missing,
        "instruction": (
            "Use only supplied sensor values and location context. Treat null values as unknown, not zero. "
            "If a nutrient reading is missing, mention it in missingReadings and avoid nutrient-specific certainty."
        ),
    }
    prompt = (
        "You are CropConnect's AI crop planning agent for Indian farms. "
        "Recommend crops that can be planted in the farmer's area using the supplied live ESP32 sensor readings, "
        "farm location, acreage, season, and planning goal. "
        "Never use hidden static crop tables or invented farm readings. Never treat missing readings as 0. "
        "Do not invent exact mandi prices. Do not claim lab certainty. "
        "If location is missing, say location is needed in the summary. "
        "Return strict JSON only with this shape: "
        "{\"crops\":[{\"name\":\"Crop\",\"category\":\"...\",\"season\":\"Kharif/Rabi/Perennial\","
        "\"cropType\":\"Food Crops/Cash Crops/Horticulture Crops/Fodder Crops\","
        "\"fit\":\"0-100%\",\"suitability\":\"...\",\"moisture_range\":[min,max],"
        "\"temp_range\":[min,max],\"humidity_range\":[min,max],\"ph_range\":[min,max],"
        "\"description\":\"short practical reason based on the readings and location\","
        "\"status_message\":\"short warning or next step\","
        "\"missingReadings\":[\"nitrogen\"]}],\"summary\":\"one sentence\"}. "
        "Recommend 6-10 crops ranked by fit. Keep numbers realistic and agronomy-safe."
    )
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(context_with_missing, ensure_ascii=False, default=str)},
    ]
