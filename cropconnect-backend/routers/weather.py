from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/weather/forecast", core.weather_forecast, methods=["GET"])
    return router
