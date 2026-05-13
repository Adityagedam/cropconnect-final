from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/", core.root, methods=["GET"])
    router.add_api_route("/api/health", core.health, methods=["GET"])
    router.add_api_route("/api/enquiries", core.enquiries, methods=["POST"])
    return router
