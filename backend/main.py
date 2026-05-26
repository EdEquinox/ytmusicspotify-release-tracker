from __future__ import annotations

import sys
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.auth_config import get_api_token, get_cors_origins, is_auth_enabled
from core.user_auth import init_user_auth, is_user_login_configured
from middleware.api_auth import ApiAuthMiddleware
from routes.artists import router as artists_router
from routes.auth import router as auth_router
from routes.errors import router as errors_router
from routes.health import router as health_router
from routes.historico import router as historico_router
from routes.releases import router as releases_router
from routes.settings import router as settings_router
from services.jobs_service import _auto_fetch_loop
from services.settings_service import _ensure_settings_schema

app = FastAPI(title="ytmusic-release-tracker-backend", docs_url=None, redoc_url=None, openapi_url=None)

cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ApiAuthMiddleware)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(artists_router)
app.include_router(releases_router)
app.include_router(errors_router)
app.include_router(historico_router)


@app.on_event("startup")
def startup_background_tasks() -> None:
    init_user_auth()
    if is_auth_enabled():
        parts = []
        if is_user_login_configured():
            parts.append("user login")
        if get_api_token():
            parts.append("API token (workers)")
        print(f"[security] Auth enabled: {', '.join(parts)}.", file=sys.stderr)
    else:
        print(
            "[security] WARNING: auth not configured — backend is open. "
            "Set APP_USERNAME/APP_PASSWORD/JWT_SECRET and API_TOKEN before exposing via Cloudflare Tunnel.",
            file=sys.stderr,
        )
    if is_auth_enabled() and not cors_origins:
        print(
            "[security] WARNING: CORS_ORIGINS is empty while API auth is on. "
            "Set CORS_ORIGINS to your frontend URL (e.g. https://tracker.example.com).",
            file=sys.stderr,
        )
    _ensure_settings_schema()
    Thread(target=_auto_fetch_loop, daemon=True).start()
