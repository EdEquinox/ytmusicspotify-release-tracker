from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException

from core import state
from models.schemas import (
    AppSettings,
    AppSettingsUpdate,
    YTMusicAuthImportPayload,
)
from services.settings_service import _read_settings, _write_settings
from services.ytmusic_service import (
    _format_ytmusic_validate_error,
    _validate_ytmusic_auth_payload,
    _ytmusic_auth_targets,
)

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings() -> AppSettings:
    with state._settings_lock:
        return _read_settings()


@router.put("/settings")
def update_settings(payload: AppSettingsUpdate) -> AppSettings:
    with state._settings_lock:
        current = _read_settings()
        updated = current.model_copy(
            update={
                "playlist_id": payload.playlist_id.strip(),
                "ytmusic_user": payload.ytmusic_user.strip(),
                "local_fetch_spacing_ms": payload.local_fetch_spacing_ms,
                "release_workers": payload.release_workers,
                "worker_idle_seconds": payload.worker_idle_seconds,
                "worker_processed_sleep_seconds": payload.worker_processed_sleep_seconds,
                "worker_backend_retry_seconds": payload.worker_backend_retry_seconds,
                "worker_album_audio_only_strict": payload.worker_album_audio_only_strict,
            }
        )
        _write_settings(updated)
    return updated


@router.post("/settings/ytmusic-auth/import")
def import_ytmusic_auth(payload: YTMusicAuthImportPayload) -> dict[str, str]:
    targets = _ytmusic_auth_targets()

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(json.dumps(payload.auth_json, ensure_ascii=True, indent=2) + "\n")
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"No write permission to {target}") from exc

    return {"status": "ok", "updated_files": ", ".join(str(item) for item in targets)}


@router.post("/settings/ytmusic-auth/validate")
def validate_ytmusic_auth() -> dict:
    targets = _ytmusic_auth_targets()
    results: list[dict[str, str | bool]] = []
    all_ok = True

    with state._settings_lock:
        app = _read_settings()
    main_user = (app.ytmusic_user or "").strip() or os.getenv("YTMUSIC_USER", "").strip() or None

    for target in targets:
        try:
            if not target.exists():
                raise FileNotFoundError(f"{target} does not exist.")
            auth_payload = json.loads(target.read_text())
            _validate_ytmusic_auth_payload(auth_payload, main_user)
            results.append({"target": str(target), "ok": True, "message": "Auth validated successfully."})
        except Exception as exc:
            all_ok = False
            results.append(
                {"target": str(target), "ok": False, "message": _format_ytmusic_validate_error(exc)}
            )

    return {"ok": all_ok, "results": results}
