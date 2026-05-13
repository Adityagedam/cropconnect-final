# AI classification, translation, parsing, and web-search helpers.
import esp32_ingest as _api

classify_farm_scope_with_ai = _api.classify_farm_scope_with_ai
google_search = _api.google_search
is_market_question = _api.is_market_question
is_plant_or_soil_question = _api.is_plant_or_soil_question
parse_ai_json = _api.parse_ai_json
selected_language = _api.selected_language
selected_language_name = _api.selected_language_name
translate_texts_with_ai = _api.translate_texts_with_ai

__all__ = [
    "classify_farm_scope_with_ai",
    "google_search",
    "is_market_question",
    "is_plant_or_soil_question",
    "parse_ai_json",
    "selected_language",
    "selected_language_name",
    "translate_texts_with_ai",
]
