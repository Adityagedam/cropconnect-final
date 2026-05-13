from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/utils/translate", core.api_translate, methods=["POST"])
    router.add_api_route("/api/ai/chat", core.ai_chat, methods=["POST"])
    router.add_api_route("/api/crops/recommend", core.crop_recommend, methods=["POST"])
    router.add_api_route("/api/ai/orchestrate", core.ai_orchestrate, methods=["POST"])
    return router
