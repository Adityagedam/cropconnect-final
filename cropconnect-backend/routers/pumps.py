from fastapi import APIRouter
from fastapi.responses import PlainTextResponse


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/api/esp32/relay-command",
        core.esp32_relay_command,
        methods=["GET"],
        response_class=PlainTextResponse,
    )
    router.add_api_route(
        "/esp32/relay-command",
        core.esp32_relay_command_short,
        methods=["GET"],
        response_class=PlainTextResponse,
    )
    router.add_api_route("/api/esp32/relay-status", core.esp32_relay_status, methods=["POST"])
    router.add_api_route("/api/esp32/relay-status/update", core.esp32_relay_status_update, methods=["GET"])
    router.add_api_route("/api/esp32/relay-status", core.get_esp32_relay_status, methods=["GET"])
    router.add_api_route("/api/pump/state", core.set_pump_state, methods=["POST"])
    router.add_api_route("/api/farm/pump-state", core.save_pump_state, methods=["POST"])
    router.add_api_route("/api/farm/pump-states", core.get_pump_states, methods=["GET"])
    router.add_api_route("/api/farm/timers", core.save_pump_timers, methods=["POST"])
    router.add_api_route("/api/farm/timers", core.get_pump_timers, methods=["GET"])
    return router
