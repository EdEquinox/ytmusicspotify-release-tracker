from __future__ import annotations

import os

import state

from config import DEFAULT_WORKERS, SETTINGS_FILE
from json_io import _read_json_object, _write_json_object
from schemas import AppSettings


def _default_settings_payload() -> dict:
    return AppSettings(
        playlist_id="",
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", "").strip(),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "").strip(),
        spotify_oauth_client_id=os.getenv("REACT_APP_SPOTIFY_CLIENT_ID", "").strip(),
        spotify_oauth_redirect_uri=os.getenv("REACT_APP_SPOTIFY_REDIRECT_URI", "").strip(),
        reverse_spotify_playlist_id="",
        reverse_poll_seconds=300,
        reverse_liked_limit=100,
        reverse_spotify_redirect_uri="http://localhost:8080/callback",
        reverse_spotify_add_to_playlist=True,
        reverse_spotiflac_enabled=False,
        reverse_spotiflac_output_dir="/data/downloads",
        reverse_spotiflac_command_template='spotiflac "{spotify_url}" "{output_dir}"',
        reverse_spotiflac_timeout_seconds=600,
        reverse_spotiflac_loop_minutes=0,
        reverse_track_spacing_ms=0,
        spotify_include_groups="album,single",
        spotify_market="",
        local_fetch_spacing_ms=120,
        release_workers=max(DEFAULT_WORKERS, 1),
        worker_idle_seconds=20,
        worker_processed_sleep_seconds=10,
        worker_backend_retry_seconds=15,
        worker_album_audio_only_strict=True,
    ).model_dump()


def _read_settings() -> AppSettings:
    raw = _read_json_object(SETTINGS_FILE, _default_settings_payload())
    return AppSettings(**raw)


def _write_settings(settings: AppSettings) -> None:
    _write_json_object(SETTINGS_FILE, settings.model_dump())


def _ensure_settings_schema() -> None:
    defaults = _default_settings_payload()
    raw = _read_json_object(SETTINGS_FILE, defaults)
    merged = {**defaults, **raw}
    try:
        _write_settings(AppSettings(**merged))
    except PermissionError:
        pass


def _effective_include_groups() -> str:
    with state._settings_lock:
        settings = _read_settings()
    return (settings.spotify_include_groups or "album,single").strip()


def _effective_spotify_market() -> str:
    with state._settings_lock:
        settings = _read_settings()
    return (settings.spotify_market or "").strip()


def _effective_release_workers() -> int:
    with state._settings_lock:
        settings = _read_settings()
    return max(int(settings.release_workers or DEFAULT_WORKERS), 1)


def _effective_local_fetch_spacing_ms() -> int:
    with state._settings_lock:
        settings = _read_settings()
    return max(int(settings.local_fetch_spacing_ms or 120), 0)


def _get_spotify_credentials() -> tuple[str, str]:
    with state._settings_lock:
        settings = _read_settings()

    client_id = (settings.spotify_client_id or "").strip() or os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = (settings.spotify_client_secret or "").strip() or os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=500,
            detail="Spotify credentials are missing. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.",
        )
    return client_id, client_secret
