from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_DAYS = 7
_SESSION_TYPE = "session"

_password_hash: bytes | None = None


def get_app_username() -> str:
    return os.getenv("APP_USERNAME", "").strip()


def get_app_password() -> str:
    return os.getenv("APP_PASSWORD", "").strip()


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("JWT_SECRET is required when APP_USERNAME/APP_PASSWORD are set.")
    return secret


def is_user_login_configured() -> bool:
    return bool(get_app_username() and get_app_password())


def init_user_auth() -> None:
    global _password_hash
    if not is_user_login_configured():
        _password_hash = None
        return
    _password_hash = bcrypt.hashpw(get_app_password().encode("utf-8"), bcrypt.gensalt(rounds=12))


def verify_user_credentials(username: str, password: str) -> bool:
    if not is_user_login_configured() or _password_hash is None:
        return False
    if username.strip() != get_app_username():
        return False
    return bcrypt.checkpw(password.encode("utf-8"), _password_hash)


def create_session_token(username: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "type": _SESSION_TYPE,
        "iat": now,
        "exp": now + timedelta(days=_JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def verify_session_token(token: str) -> bool:
    if not is_user_login_configured():
        return False
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return False
    return payload.get("type") == _SESSION_TYPE and payload.get("sub") == get_app_username()
