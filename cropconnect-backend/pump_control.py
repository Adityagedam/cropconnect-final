from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

RELAY_COMMAND_STATE: dict[int, bool] = {index: False for index in range(1, 9)}
RELAY_APPLIED_STATE: dict[int, bool] = {index: False for index in range(1, 9)}
RELAY_STATUS_UPDATED_AT = ""


class PumpStateIn(BaseModel):
    pump_id: str = Field(default="pump1", min_length=1, max_length=40)
    on: bool
    device_id: str | None = Field(default="", max_length=80)
    runtime: int | None = Field(default=0, ge=0)
    schedule: dict[str, Any] = Field(default_factory=dict)


def pump_number(pump_id: str) -> str:
    digits = "".join(ch for ch in pump_id if ch.isdigit())
    return digits or pump_id


def update_relay_command_state(pump_id: str, on: bool) -> None:
    try:
        relay_number = int(pump_number(pump_id))
    except ValueError:
        return

    if 1 <= relay_number <= 8:
        RELAY_COMMAND_STATE[relay_number] = on


def relay_command_text(states: dict[int, bool] | None = None) -> str:
    desired_states = states or RELAY_COMMAND_STATE
    return " ".join(
        f"{relay_number}{'on' if desired_states.get(relay_number, False) else 'off'}"
        for relay_number in range(1, 9)
    )


def update_relay_applied_state(states: dict[int, bool]) -> None:
    global RELAY_STATUS_UPDATED_AT
    for relay_number, on in states.items():
        if 1 <= relay_number <= 8:
            RELAY_APPLIED_STATE[relay_number] = on
    RELAY_STATUS_UPDATED_AT = datetime.now(timezone.utc).isoformat()


def relay_status_payload(desired_states: dict[int, bool] | None = None) -> dict[str, Any]:
    desired = desired_states or RELAY_COMMAND_STATE
    return {
        "desired": {
            str(relay_number): desired.get(relay_number, False)
            for relay_number in range(1, 9)
        },
        "applied": {
            str(relay_number): RELAY_APPLIED_STATE[relay_number]
            for relay_number in range(1, 9)
        },
        "updated_at": RELAY_STATUS_UPDATED_AT,
    }
