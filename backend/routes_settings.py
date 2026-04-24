from __future__ import annotations

import json
import os
from base64 import b64encode
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException

from config import SPOTIFY_ACCOUNTS_URL
from jobs_service import _is_valid_hhmm
from schemas import (
    AppSettings,
    AppSettingsUpdate,
    ReverseSpotifyOAuthCompletePayload,
    YTMusicAuthImportPayload,
)
import state
from settings_service import _read_settings, _write_settings
from spotify_api import _reverse_spotify_cache_path
from ytmusic_service import (
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
    if not _is_valid_hhmm(payload.auto_fetch_time):
        raise HTTPException(status_code=400, detail="auto_fetch_time must use HH:MM (24h)")
    with state._settings_lock:
        current = _read_settings()
        updated = current.model_copy(
            update={
                "playlist_id": payload.playlist_id.strip(),
                "auto_fetch_enabled": payload.auto_fetch_enabled,
                "auto_fetch_time": payload.auto_fetch_time,
                "auto_fetch_window_days": payload.auto_fetch_window_days,
                "spotify_include_groups": payload.spotify_include_groups.strip() or "album,single",
                "spotify_market": payload.spotify_market.strip(),
                "local_fetch_spacing_ms": payload.local_fetch_spacing_ms,
                "release_workers": payload.release_workers,
                "worker_idle_seconds": payload.worker_idle_seconds,
                "worker_processed_sleep_seconds": payload.worker_processed_sleep_seconds,
                "worker_backend_retry_seconds": payload.worker_backend_retry_seconds,
                "worker_album_audio_only_strict": payload.worker_album_audio_only_strict,
                "spotify_client_id": payload.spotify_client_id.strip(),
                "spotify_client_secret": payload.spotify_client_secret.strip(),
                "spotify_oauth_client_id": payload.spotify_oauth_client_id.strip(),
                "spotify_oauth_redirect_uri": payload.spotify_oauth_redirect_uri.strip(),
                "reverse_spotify_playlist_id": payload.reverse_spotify_playlist_id.strip(),
                "reverse_poll_seconds": payload.reverse_poll_seconds,
                "reverse_liked_limit": payload.reverse_liked_limit,
                "reverse_spotify_redirect_uri": payload.reverse_spotify_redirect_uri.strip(),
                "reverse_spotify_add_to_playlist": payload.reverse_spotify_add_to_playlist,
                "reverse_spotiflac_enabled": payload.reverse_spotiflac_enabled,
                "reverse_spotiflac_output_dir": payload.reverse_spotiflac_output_dir.strip() or "/data/downloads",
                "reverse_spotiflac_command_template": payload.reverse_spotiflac_command_template.strip()
                or 'spotiflac "{spotify_url}" "{output_dir}"',
                "reverse_spotiflac_timeout_seconds": payload.reverse_spotiflac_timeout_seconds,
                "reverse_spotiflac_loop_minutes": payload.reverse_spotiflac_loop_minutes,
                "reverse_track_spacing_ms": payload.reverse_track_spacing_ms,
            }
        )
        _write_settings(updated)
    return updated


@router.post("/settings/reverse-spotify-oauth/complete")
def complete_reverse_spotify_oauth(payload: ReverseSpotifyOAuthCompletePayload) -> dict[str, str]:
    response_url = payload.response_url.strip()
    parsed = urlparse(response_url)
    code = parse_qs(parsed.query).get("code", [""])[0].strip()
    if not code:
        raise HTTPException(status_code=400, detail="response_url must include ?code=...")

    with state._settings_lock:
        settings = _read_settings()
    client_id = (settings.spotify_oauth_client_id or settings.spotify_client_id or "").strip() or os.getenv(
        "SPOTIFY_CLIENT_ID", ""
    ).strip()
    client_secret = (settings.spotify_client_secret or "").strip() or os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    redirect_uri = (
        settings.reverse_spotify_redirect_uri
        or settings.spotify_oauth_redirect_uri
        or os.getenv("REVERSE_SPOTIFY_REDIRECT_URI", "")
        or "http://127.0.0.1:8080/callback"
    ).strip()

    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Spotify client_id/client_secret missing in settings/env.")

    basic = b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    request = Request(
        url=SPOTIFY_ACCOUNTS_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=body,
    )
    try:
        with urlopen(request, timeout=20) as response:
            token_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise HTTPException(status_code=400, detail=f"Spotify token exchange failed: {detail}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"Spotify token exchange network error: {exc}") from exc

    access_token = str(token_payload.get("access_token", "")).strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="Spotify token exchange returned no access_token.")

    expires_in = int(token_payload.get("expires_in") or 3600)
    token_payload["expires_at"] = int(datetime.now(UTC).timestamp()) + expires_in

    cache_path = _reverse_spotify_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(token_payload, ensure_ascii=True, indent=2) + "\n")
    return {"status": "ok", "message": "Reverse Spotify OAuth token cached successfully."}


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
    ytmusic_user = os.getenv("YTMUSIC_USER", "").strip() or None
    results: list[dict[str, str | bool]] = []
    all_ok = True

    for target in targets:
        try:
            if not target.exists():
                raise FileNotFoundError(f"{target} does not exist.")
            auth_payload = json.loads(target.read_text())
            _validate_ytmusic_auth_payload(auth_payload, ytmusic_user)
            results.append({"target": str(target), "ok": True, "message": "Auth validated successfully."})
        except Exception as exc:
            all_ok = False
            results.append(
                {"target": str(target), "ok": False, "message": _format_ytmusic_validate_error(exc)}
            )

    return {"ok": all_ok, "results": results}
