from typing import Any

from pydantic import BaseModel, Field


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
    """Compatibility hook.

    Desired relay commands are persisted in MySQL pump_states and fetched per
    device. Keeping this as a no-op prevents process memory from becoming an
    accidental source of truth after deploys or restarts.
    """
    return None


def relay_command_text(states: dict[int, bool]) -> str:
    desired_states = states or {}
    return " ".join(
        f"{relay_number}{'on' if desired_states.get(relay_number, False) else 'off'}"
        for relay_number in range(1, 9)
    )


def update_relay_applied_state(states: dict[int, bool]) -> None:
    """Compatibility hook.

    Applied relay status is stored in MySQL relay_statuses by the API layer.
    This function intentionally does not keep process-local state.
    """
    return None


def relay_status_payload(desired_states: dict[int, bool] | None = None) -> dict[str, Any]:
    desired = desired_states or {}
    return {
        "desired": {
            str(relay_number): desired.get(relay_number, False)
            for relay_number in range(1, 9)
        },
        "applied": {
            str(relay_number): None
            for relay_number in range(1, 9)
        },
        "updated_at": None,
    }
