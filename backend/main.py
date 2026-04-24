from __future__ import annotations

from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobs_service import _auto_fetch_loop
from settings_service import _ensure_settings_schema
from routes_artists import router as artists_router
from routes_errors import router as errors_router
from routes_health import router as health_router
from routes_historico import router as historico_router
from routes_releases import router as releases_router
from routes_settings import router as settings_router
from routes_spotify import router as spotify_router

app = FastAPI(title="ytmusic-release-tracker-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(settings_router)
app.include_router(artists_router)
app.include_router(spotify_router)
app.include_router(releases_router)
app.include_router(errors_router)
app.include_router(historico_router)


@app.on_event("startup")
def startup_background_tasks() -> None:
    _ensure_settings_schema()
    Thread(target=_auto_fetch_loop, daemon=True).start()
