from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/public/sensors/latest", core.public_latest_landing_sensor, methods=["GET"])
    router.add_api_route("/api/telemetry/ingest", core.ingest_telemetry, methods=["POST"])
    router.add_api_route("/api/telemetry/ingest", core.ingest_telemetry_get, methods=["GET"])
    router.add_api_route("/data", core.receive, methods=["POST"])
    router.add_api_route("/data", core.receive_get, methods=["GET"])
    router.add_api_route("/api/sensors/latest", core.latest_sensors, methods=["GET"])
    router.add_api_route("/api/sensors/history", core.sensor_history, methods=["GET"])
    router.add_api_route("/api/esp32/device-key", core.get_esp32_device_key, methods=["GET"])
    router.add_api_route("/api/esp32/device-key", core.create_esp32_device_key, methods=["POST"])
    router.add_api_route("/api/esp32/device-key/rotate", core.rotate_esp32_device_key_endpoint, methods=["POST"])
    return router
