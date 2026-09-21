from __future__ import annotations

from core import state
from core.config import DEFAULT_WORKERS, SETTINGS_FILE
from core.json_io import _read_json_object, _write_json_object
from models.schemas import AppSettings


def _default_settings_payload() -> dict:
    return AppSettings(
        playlist_id="",
        ytmusic_user="",
        local_fetch_spacing_ms=120,
        release_workers=max(DEFAULT_WORKERS, 1),
        worker_idle_seconds=20,
        worker_processed_sleep_seconds=10,
        worker_backend_retry_seconds=15,
        worker_album_audio_only_strict=True,
    ).model_dump()


def _read_settings() -> AppSettings:
    raw = _read_json_object(SETTINGS_FILE, _default_settings_payload())
    # Ignore legacy reverse_* keys that may still exist in settings.json.
    return AppSettings.model_validate(raw)


def _write_settings(settings: AppSettings) -> None:
    _write_json_object(SETTINGS_FILE, settings.model_dump())


def _persist_last_releases_fetch_end_date(end_date_iso: str) -> None:
    """Grava a data «Fim» do último fetch de releases concluído (YYYY-MM-DD) para pré-preencher a página Releases."""
    end = (end_date_iso or "").strip()
    if not end:
        return
    with state._settings_lock:
        current = _read_settings()
        _write_settings(current.model_copy(update={"last_releases_fetch_end_date": end}))


def _ensure_settings_schema() -> None:
    defaults = _default_settings_payload()
    raw = _read_json_object(SETTINGS_FILE, defaults)
    merged = {**defaults, **raw}
    try:
        _write_settings(AppSettings.model_validate(merged))
    except PermissionError:
        pass


def _effective_release_workers() -> int:
    with state._settings_lock:
        settings = _read_settings()
    return max(int(settings.release_workers or DEFAULT_WORKERS), 1)


def _effective_local_fetch_spacing_ms() -> int:
    with state._settings_lock:
        settings = _read_settings()
    return max(int(settings.local_fetch_spacing_ms or 120), 0)
