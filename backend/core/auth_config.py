from __future__ import annotations

import os

from core.user_auth import is_user_login_configured


def get_api_token() -> str:
    return os.getenv("API_TOKEN", "").strip()


def is_auth_disabled() -> bool:
    return os.getenv("API_AUTH_DISABLED", "").strip().lower() in ("1", "true", "yes")


def is_auth_enabled() -> bool:
    if is_auth_disabled():
        return False
    return bool(get_api_token()) or is_user_login_configured()


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    single = os.getenv("CORS_ORIGIN", "").strip()
    if single:
        return [single]
    if is_auth_enabled():
        return []
    return ["*"]
