from __future__ import annotations

from email.utils import parseaddr
from typing import Any

from pydantic import BaseModel, Field, field_validator

TRANSLATION_TEXT_LIMIT = 1000
TRANSLATION_BATCH_LIMIT = 40
TRANSLATION_TOTAL_CHAR_LIMIT = 12000


def validate_email_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    _name, parsed_email = parseaddr(text)
    local_part, separator, domain = parsed_email.partition("@")
    if (
        parsed_email != text
        or not separator
        or not local_part
        or not domain
        or any(char.isspace() for char in parsed_email)
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
        or len(parsed_email) > 254
    ):
        raise ValueError("Enter a valid email address")
    return parsed_email


class EmailValidatedModel(BaseModel):
    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def validate_email_field(cls, value: Any) -> Any:
        if value is None or value == "":
            return value
        return validate_email_text(value)


class TelemetryIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    soil_moisture: float | None = Field(default=None, ge=0, le=100)
    humidity: float | None = Field(default=None, ge=0, le=100)
    temperature: float | None = Field(default=None, ge=-20, le=80)
    ph: float | None = Field(default=None, ge=0, le=14)
    nitrogen: float | None = Field(default=None, ge=0)
    phosphorus: float | None = Field(default=None, ge=0)
    potassium: float | None = Field(default=None, ge=0)


class EnquiryIn(EmailValidatedModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(default="", max_length=40)
    organization: str | None = Field(default="", max_length=160)
    message: str = Field(min_length=1, max_length=4000)


class ChatIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    message: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="en", max_length=16)
    input_language: str = Field(default="en", max_length=16)
    device_id: str | None = Field(default="", max_length=80)
    sensor_data: dict[str, Any] = Field(default_factory=dict)
    market_data: dict[str, Any] = Field(default_factory=dict)
    weather_data: dict[str, Any] = Field(default_factory=dict)
    location: str | None = Field(default="", max_length=160)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


class AuthSignupIn(EmailValidatedModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    phone: str | None = Field(default="", max_length=30)
    state: str | None = Field(default="", max_length=120)
    location: str | None = Field(default="", max_length=255)
    land_size: float | None = Field(default=None, ge=0)
    location_type: str | None = Field(default="city", max_length=20)
    district: str | None = Field(default="", max_length=120)
    city: str | None = Field(default="", max_length=120)
    village: str | None = Field(default="", max_length=120)
    sensors: str | None = Field(default="0", max_length=20)
    pumps: str | None = Field(default="0", max_length=20)
    sensor_setup_complete: bool = False
    sensor_setup_status: str | None = Field(default="pending", max_length=40)


class AuthLoginIn(EmailValidatedModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class AuthPasswordResetRequestIn(EmailValidatedModel):
    email: str = Field(min_length=3, max_length=255)


class AuthPasswordResetConfirmIn(EmailValidatedModel):
    email: str = Field(min_length=3, max_length=255)
    token: str = Field(min_length=20, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class AuthProfileUpdateIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    state: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    land_size: float | None = Field(default=None, ge=0)
    location_type: str | None = Field(default=None, max_length=20)
    district: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    sensor_device_id: str | None = Field(default=None, max_length=80)
    sensors: str | None = Field(default=None, max_length=20)
    pumps: str | None = Field(default=None, max_length=20)
    sensor_setup_complete: bool | None = None
    sensor_setup_status: str | None = Field(default=None, max_length=40)


class PumpStateSaveIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    device_id: str | None = Field(default="", max_length=80)
    pump_id: str = Field(min_length=1, max_length=40)
    on: bool
    runtime: int | None = Field(default=0, ge=0)
    schedule: dict[str, Any] = Field(default_factory=dict)
    sent_to_esp32: bool = False
    message: str | None = Field(default="", max_length=255)


class RelayStatusIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    relays: dict[str, bool] = Field(default_factory=dict)


class PumpTimersSaveIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    timers: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class TranslateIn(BaseModel):
    text: str | None = Field(default=None, max_length=TRANSLATION_TEXT_LIMIT)
    texts: list[str] | None = Field(default=None, max_length=TRANSLATION_BATCH_LIMIT)
    target_lang: str = Field(min_length=2, max_length=40)

    @field_validator("texts")
    @classmethod
    def validate_text_items(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        total_characters = 0
        normalized_items: list[str] = []
        for item in value:
            text = str(item or "")
            if len(text) > TRANSLATION_TEXT_LIMIT:
                raise ValueError(f"Each translation item must be {TRANSLATION_TEXT_LIMIT} characters or fewer")
            total_characters += len(text)
            normalized_items.append(text)
        if total_characters > TRANSLATION_TOTAL_CHAR_LIMIT:
            raise ValueError(f"Translation batch must be {TRANSLATION_TOTAL_CHAR_LIMIT} characters or fewer")
        return normalized_items


class CropRecommendIn(BaseModel):
    goal: str = Field(default="balanced", max_length=40)
    season: str | None = Field(default="", max_length=80)
    language: str | None = Field(default="en", max_length=20)
    device_id: str | None = Field(default="", max_length=80)
    sensor_source: str | None = Field(default="", max_length=40)


class MarketInsightIn(BaseModel):
    language: str | None = Field(default="en", max_length=20)
    objective: str = Field(default="Give practical selling guidance from live local mandi records", max_length=300)


class AIOrchestrateIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default="", max_length=160)
    language: str | None = Field(default="en", max_length=20)
    sensor_data: dict[str, Any] = Field(default_factory=dict)
    pump_data: dict[str, Any] = Field(default_factory=dict)
    timers: dict[str, Any] = Field(default_factory=dict)
    weather_data: dict[str, Any] | None = Field(default=None)
    market_data: dict[str, Any] | None = Field(default=None)
    objective: str = Field(default="Optimize farm health and irrigation decisions", max_length=500)


class DashboardSnapshotIn(EmailValidatedModel):
    user_id: int | None = Field(default=None, ge=1)
    email: str | None = Field(default=None, max_length=255)
    device_id: str | None = Field(default="", max_length=80)
    source: str | None = Field(default="dashboard", max_length=40)
    sensor_data: dict[str, Any] = Field(default_factory=dict)
    pump_data: dict[str, Any] = Field(default_factory=dict)
    timers: dict[str, Any] = Field(default_factory=dict)
    weather_data: dict[str, Any] | None = Field(default=None)
    market_data: dict[str, Any] | None = Field(default=None)
    telemetry_packet: dict[str, Any] = Field(default_factory=dict)
