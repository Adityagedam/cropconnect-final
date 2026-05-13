from fastapi import APIRouter


def create_router(core) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/api/auth/signup", core.auth_signup, methods=["POST"])
    router.add_api_route("/api/auth/login", core.auth_login, methods=["POST"])
    router.add_api_route("/api/auth/logout", core.auth_logout, methods=["POST"])
    router.add_api_route("/api/auth/csrf", core.auth_csrf, methods=["GET"])
    router.add_api_route("/api/auth/profile", core.auth_profile, methods=["GET"])
    router.add_api_route("/api/auth/profile", core.auth_profile_update, methods=["POST"])
    router.add_api_route("/api/auth/password-reset-request", core.auth_password_reset_request, methods=["POST"])
    router.add_api_route("/api/auth/password-reset-confirm", core.auth_password_reset_confirm, methods=["POST"])
    return router
