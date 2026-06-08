from __future__ import annotations

from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.artists import router as artists_router
from routes.errors import router as errors_router
from routes.health import router as health_router
from routes.historico import router as historico_router
from routes.releases import router as releases_router
from routes.settings import router as settings_router
from services.jobs_service import _auto_fetch_loop
from services.settings_service import _ensure_settings_schema

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
app.include_router(releases_router)
app.include_router(errors_router)
app.include_router(historico_router)


@app.on_event("startup")
def startup_background_tasks() -> None:
    _ensure_settings_schema()
    Thread(target=_auto_fetch_loop, daemon=True).start()
