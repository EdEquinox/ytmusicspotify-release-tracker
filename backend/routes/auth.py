from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.user_auth import (
    create_session_token,
    get_app_username,
    is_user_login_configured,
    verify_user_credentials,
)
from models.schemas import LoginPayload, LoginResponse

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginPayload) -> LoginResponse:
    if not is_user_login_configured():
        raise HTTPException(
            status_code=503,
            detail="User login is not configured. Set APP_USERNAME, APP_PASSWORD and JWT_SECRET.",
        )
    if not verify_user_credentials(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_session_token(get_app_username())
    return LoginResponse(access_token=token)


@router.get("/auth/verify")
def verify_session() -> dict[str, bool]:
    """Requires valid session JWT or API token when auth is enabled."""
    return {"ok": True}
