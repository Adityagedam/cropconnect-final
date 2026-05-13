from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/market/prices", core.market_prices, methods=["GET"])
    router.add_api_route("/api/market/insights", core.market_insights, methods=["POST"])
    return router
