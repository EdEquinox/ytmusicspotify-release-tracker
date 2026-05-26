from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.auth_config import get_api_token, is_auth_enabled
from core.user_auth import is_user_login_configured, verify_session_token

_PUBLIC_PATHS = frozenset({"/health", "/auth/login"})


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _is_authorized(provided: str) -> bool:
    if not provided:
        return False
    api_token = get_api_token()
    if api_token and provided == api_token:
        return True
    if is_user_login_configured() and verify_session_token(provided):
        return True
    return False


class ApiAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not is_auth_enabled():
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        provided = _extract_bearer_token(request)
        if not _is_authorized(provided):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized. Sign in or provide a valid API token."},
            )

        return await call_next(request)
