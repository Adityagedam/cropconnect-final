from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/farm/chat-history", core.get_chat_history, methods=["GET"])
    router.add_api_route("/api/farm/snapshot", core.save_dashboard_snapshot, methods=["POST"])
    router.add_api_route("/api/farm/snapshot/latest", core.get_latest_dashboard_snapshot, methods=["GET"])
    return router
