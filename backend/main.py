from __future__ import annotations

import json
import os
import tempfile
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from ytmusicapi import YTMusic
    from ytmusicapi.helpers import get_authorization, sapisid_from_cookie
except Exception:  # pragma: no cover - optional dependency in some environments
    YTMusic = None
    get_authorization = None
    sapisid_from_cookie = None


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ARTISTS_FILE = DATA_DIR / "artists.json"
ERRORS_FILE = DATA_DIR / "errors.json"
RELEASES_FILE = DATA_DIR / "releases.json"
RELEASE_FETCH_STATE_FILE = DATA_DIR / "release_fetch_state.json"
CSV_RELEASES_FILE = DATA_DIR / "csv_releases.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORICO_FILE = DATA_DIR / "historico.json"
SPOTIFY_ACCOUNTS_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
DEFAULT_WORKERS = 10

_spotify_token: str | None = None
_spotify_token_expires_at: float = 0.0
_spotify_backoff_until: float = 0.0
_release_jobs: dict[str, dict] = {}
_release_jobs_lock = Lock()
_local_fetch_jobs: dict[str, dict] = {}
_local_fetch_jobs_lock = Lock()
_settings_lock = Lock()

app = FastAPI(title="ytmusic-release-tracker-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ArtistCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    image_url: str | None = None


class SyncErrorCreate(BaseModel):
    track_name: str = Field(min_length=1)
    artist_name: str = Field(min_length=1)
    album_name: str | None = None
    reason: str = Field(min_length=1)
    spotify_url_manual: str | None = None
    tidal_url_manual: str | None = None


class SyncErrorItem(SyncErrorCreate):
    id: str
    created_at: str
    attempts: int = Field(default=1, ge=1)


class SyncErrorLinksUpdate(BaseModel):
    spotify_url_manual: str | None = None
    tidal_url_manual: str | None = None


class SpotifyArtistItem(BaseModel):
    id: str
    name: str
    image_url: str | None = None


class ReleaseItem(BaseModel):
    id: str
    name: str
    artist_name: str
    release_date: str
    album_type: str
    spotify_url: str | None = None
    tracked_artist_id: str | None = None
    image_url: str | None = None
    matched_artists: list[str] = []
    has_non_primary_match: bool = False
    fetched_at: str | None = None


class AlbumTrackItem(BaseModel):
    id: str
    name: str
    artist_name: str
    spotify_url: str | None = None
    duration_ms: int | None = None


class ReleaseSyncJob(BaseModel):
    id: str
    status: str
    progress: int
    processed_artists: int
    total_artists: int
    start_date: str
    end_date: str
    created_at: str
    updated_at: str
    releases: list[ReleaseItem] = []
    error: str | None = None


class CsvReleaseAddPayload(BaseModel):
    release_id: str | None = None
    id: str | None = None
    name: str | None = None
    artist_name: str | None = None
    album_type: str = "single"
    spotify_url: str | None = None


class LocalFetchJob(BaseModel):
    id: str
    status: str
    period: str
    progress: int
    processed_artists: int
    total_artists: int
    fetched_releases: int
    stored_releases: int
    start_date: str | None = None
    end_date: str | None = None
    created_at: str
    updated_at: str
    error: str | None = None


class AppSettings(BaseModel):
    playlist_id: str = ""
    auto_fetch_enabled: bool = False
    auto_fetch_time: str = "04:00"
    auto_fetch_window_days: int = 1
    spotify_include_groups: str = "album,single"
    spotify_market: str = ""
    local_fetch_spacing_ms: int = 120
    release_workers: int = 10
    worker_idle_seconds: int = 20
    worker_processed_sleep_seconds: int = 10
    worker_backend_retry_seconds: int = 15
    worker_album_audio_only_strict: bool = True
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_oauth_client_id: str = ""
    spotify_oauth_redirect_uri: str = ""
    reverse_spotify_playlist_id: str = ""
    reverse_poll_seconds: int = 300
    reverse_liked_limit: int = 100
    reverse_spotify_redirect_uri: str = "http://localhost:8080/callback"
    reverse_spotify_add_to_playlist: bool = True
    reverse_spotiflac_enabled: bool = False
    reverse_spotiflac_output_dir: str = "/data/downloads"
    reverse_spotiflac_command_template: str = (
        'spotiflac "{spotify_url}" "{output_dir}"'
    )
    reverse_spotiflac_timeout_seconds: int = 600
    reverse_spotiflac_loop_minutes: int = 0
    reverse_track_spacing_ms: int = 0
    last_auto_fetch_date: str | None = None


class AppSettingsUpdate(BaseModel):
    playlist_id: str = ""
    auto_fetch_enabled: bool = False
    auto_fetch_time: str = "04:00"
    auto_fetch_window_days: int = Field(default=1, ge=1, le=30)
    spotify_include_groups: str = "album,single"
    spotify_market: str = ""
    local_fetch_spacing_ms: int = Field(default=120, ge=0, le=5000)
    release_workers: int = Field(default=10, ge=1, le=30)
    worker_idle_seconds: int = Field(default=20, ge=5, le=3600)
    worker_processed_sleep_seconds: int = Field(default=10, ge=1, le=600)
    worker_backend_retry_seconds: int = Field(default=15, ge=5, le=600)
    worker_album_audio_only_strict: bool = True
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_oauth_client_id: str = ""
    spotify_oauth_redirect_uri: str = ""
    reverse_spotify_playlist_id: str = ""
    reverse_poll_seconds: int = Field(default=300, ge=30, le=86400)
    reverse_liked_limit: int = Field(default=100, ge=1, le=5000)
    reverse_spotify_redirect_uri: str = "http://localhost:8080/callback"
    reverse_spotify_add_to_playlist: bool = True
    reverse_spotiflac_enabled: bool = False
    reverse_spotiflac_output_dir: str = "/data/downloads"
    reverse_spotiflac_command_template: str = (
        'spotiflac "{spotify_url}" "{output_dir}"'
    )
    reverse_spotiflac_timeout_seconds: int = Field(default=600, ge=10, le=86400)
    reverse_spotiflac_loop_minutes: int = Field(default=0, ge=0, le=1440)
    reverse_track_spacing_ms: int = Field(default=0, ge=0, le=30000)


class ArtistsImportPayload(BaseModel):
    artists: list[ArtistCreate]
    replace: bool = False


class YTMusicAuthImportPayload(BaseModel):
    auth_json: dict


class HistoricoItem(BaseModel):
    id: str = Field(min_length=1)
    artista: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    created_at: str | None = None


class ReverseSpotifyOAuthCompletePayload(BaseModel):
    response_url: str = Field(min_length=1)


def _ytmusic_auth_targets() -> list[Path]:
    auth_path = Path(os.getenv("YTMUSIC_AUTH_FILE", "/data/ytmusic_auth.json")).resolve()
    reverse_auth_path = Path(
        os.getenv("REVERSE_YTMUSIC_AUTH_FILE", str(auth_path))
    ).resolve()
    targets = [auth_path]
    if reverse_auth_path not in targets:
        targets.append(reverse_auth_path)
    return targets


def _validate_ytmusic_auth_payload(auth_payload: dict, ytmusic_user: str | None = None) -> None:
    if YTMusic is None or get_authorization is None or sapisid_from_cookie is None:
        raise HTTPException(
            status_code=500,
            detail="ytmusicapi is not installed on backend. Add it to backend dependencies.",
        )

    if not isinstance(auth_payload, dict) or not auth_payload:
        raise ValueError("Auth payload must be a non-empty JSON object.")

    if "cookie" in auth_payload:
        cookie = str(auth_payload.get("cookie", "")).strip()
        origin = str(auth_payload.get("origin", "https://music.youtube.com")).strip()
        if not cookie:
            raise ValueError("Missing cookie in auth payload.")
        sapisid = sapisid_from_cookie(cookie)
        authorization = get_authorization(f"{sapisid} {origin}")
        headers = {
            "cookie": cookie,
            "origin": origin,
            "user-agent": str(auth_payload.get("user-agent", "")),
            "x-goog-authuser": str(auth_payload.get("x-goog-authuser", "0")),
            "x-goog-visitor-id": str(auth_payload.get("x-goog-visitor-id", "")),
            "authorization": authorization,
        }
        client = YTMusic(auth=headers, user=ytmusic_user or None)
        client.get_liked_songs(limit=1)
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=True, encoding="utf-8") as handle:
        handle.write(json.dumps(auth_payload, ensure_ascii=True))
        handle.flush()
        client = YTMusic(auth=handle.name, user=ytmusic_user or None)
        client.get_liked_songs(limit=1)


def _format_ytmusic_validate_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if (
        "sign in" in lowered
        or "twocolumnbrowseresultsrenderer" in lowered
        or "looking for what you’ve liked" in lowered
        or "looking for what you've liked" in lowered
    ):
        return (
            "Auth invalida/expirada para YTMusic (resposta de sign-in). "
            "Reexporta o JSON de browser auth e importa novamente em Settings."
        )
    return message


def _ensure_data_file(path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text().strip():
        path.write_text("[]\n")


def _ensure_data_object_file(path: Path, default_payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text().strip():
        path.write_text(json.dumps(default_payload, ensure_ascii=True, indent=2) + "\n")


def _read_json_list(path: Path) -> list[dict]:
    _ensure_data_file(path)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in {path.name}") from exc

    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"{path.name} must contain a JSON array")
    return data


def _write_json_list(path: Path, payload: list[dict]) -> None:
    _ensure_data_file(path)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _read_json_object(path: Path, default_payload: dict) -> dict:
    _ensure_data_object_file(path, default_payload)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in {path.name}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail=f"{path.name} must contain a JSON object")
    return data


def _write_json_object(path: Path, payload: dict) -> None:
    _ensure_data_object_file(path, payload)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


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
        # In some Docker setups /data can be mounted read-only or with root-only ownership.
        # Do not fail app startup; keep running with the readable settings payload.
        pass


def _effective_include_groups() -> str:
    with _settings_lock:
        settings = _read_settings()
    return (settings.spotify_include_groups or "album,single").strip()


def _effective_spotify_market() -> str:
    with _settings_lock:
        settings = _read_settings()
    return (settings.spotify_market or "").strip()


def _effective_release_workers() -> int:
    with _settings_lock:
        settings = _read_settings()
    return max(int(settings.release_workers or DEFAULT_WORKERS), 1)


def _effective_local_fetch_spacing_ms() -> int:
    with _settings_lock:
        settings = _read_settings()
    return max(int(settings.local_fetch_spacing_ms or 120), 0)


def _get_spotify_credentials() -> tuple[str, str]:
    with _settings_lock:
        settings = _read_settings()

    client_id = (settings.spotify_client_id or "").strip() or os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = (settings.spotify_client_secret or "").strip() or os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Spotify credentials are missing. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.",
        )
    return client_id, client_secret


def _reverse_spotify_cache_path() -> Path:
    raw = os.getenv("REVERSE_SPOTIFY_CACHE_PATH", "/data/spotify_oauth_cache_reverse.json").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / raw
    return path


def _spotify_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: bytes | None = None,
    retries: int = 2,
) -> dict:
    import time

    global _spotify_backoff_until
    now = time.time()
    if now < _spotify_backoff_until:
        remaining = int(_spotify_backoff_until - now)
        raise HTTPException(
            status_code=429,
            detail=f"Spotify rate limit cooldown active. Retry after {remaining}s.",
        )

    request = Request(url=url, method=method, headers=headers or {}, data=body)

    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                retry_after = int(exc.headers.get("Retry-After", "2"))
                _spotify_backoff_until = max(_spotify_backoff_until, time.time() + max(retry_after, 1))
                # Keep retries bounded so request loop does not block forever.
                time.sleep(min(max(retry_after, 1), 3))
                continue
            if exc.code >= 500 and attempt < retries:
                time.sleep(1 + attempt)
                continue
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After", "unknown")
                retry_after_int = int(retry_after) if str(retry_after).isdigit() else 2
                _spotify_backoff_until = max(_spotify_backoff_until, time.time() + max(retry_after_int, 1))
                raise HTTPException(
                    status_code=429,
                    detail=f"Spotify rate limit reached (429). Retry-After: {retry_after}s.",
                ) from exc
            raise HTTPException(status_code=502, detail=f"Spotify request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt < retries:
                time.sleep(1 + attempt)
                continue
            raise HTTPException(status_code=502, detail=f"Spotify network error: {exc}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Spotify request failed: {exc}") from exc

    raise HTTPException(status_code=502, detail="Spotify request failed after retries")


def _get_spotify_access_token() -> str:
    import time

    global _spotify_token, _spotify_token_expires_at
    if _spotify_token and time.time() < _spotify_token_expires_at:
        return _spotify_token

    client_id, client_secret = _get_spotify_credentials()
    basic = b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    body = urlencode({"grant_type": "client_credentials"}).encode("utf-8")

    payload = _spotify_request(
        SPOTIFY_ACCOUNTS_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=body,
    )

    token = payload.get("access_token")
    expires_in = int(payload.get("expires_in", 3600))
    if not token:
        raise HTTPException(status_code=502, detail="Failed to obtain Spotify access token")

    _spotify_token = token
    _spotify_token_expires_at = time.time() + max(expires_in - 60, 60)
    return token


def _normalize_release_date(date_value: str, precision: str) -> datetime:
    if precision == "year":
        return datetime.fromisoformat(f"{date_value}-01-01")
    if precision == "month":
        return datetime.fromisoformat(f"{date_value}-01")
    return datetime.fromisoformat(date_value)


def _fetch_artist_releases(
    access_token: str,
    artist_id: str,
    start_dt: datetime,
    end_dt: datetime,
    tracked_artist_name: str | None = None,
    swallow_errors: bool = True,
) -> list[ReleaseItem]:
    # Keep request volume low by default; can be overridden with env var.
    include_groups = _effective_include_groups()
    params_payload = {"include_groups": include_groups, "limit": 50}
    spotify_market = _effective_spotify_market()
    if spotify_market:
        params_payload["market"] = spotify_market
    params = urlencode(params_payload)
    next_url = f"{SPOTIFY_API_URL}/artists/{artist_id}/albums?{params}"
    releases: list[ReleaseItem] = []

    fetch_timestamp = datetime.now(UTC).isoformat()
    while next_url:
        try:
            payload = _spotify_request(next_url, headers={"Authorization": f"Bearer {access_token}"}, retries=1)
        except HTTPException:
            # For bulk jobs we can skip failing artists, but for per-artist fetch we should
            # surface the real upstream issue to help troubleshooting.
            if swallow_errors:
                return releases
            raise
        items = payload.get("items", [])

        for album in items:
            release_date = album.get("release_date")
            precision = album.get("release_date_precision", "day")
            if not release_date:
                continue

            try:
                normalized_date = _normalize_release_date(release_date, precision)
            except ValueError:
                continue

            if normalized_date < start_dt:
                continue
            if normalized_date > end_dt:
                continue

            album_id = album.get("id")
            if not album_id:
                continue

            artists_list = album.get("artists", [])
            first_artist = artists_list[0]["name"] if artists_list else "Unknown Artist"
            first_artist_id = artists_list[0]["id"] if artists_list else None
            spotify_url = (album.get("external_urls") or {}).get("spotify")
            images = album.get("images") or []
            image_url = images[0].get("url") if images else None
            matched_name = tracked_artist_name or first_artist
            is_primary_match = first_artist_id == artist_id
            releases.append(
                ReleaseItem(
                    id=album_id,
                    name=album.get("name", "Unknown Release"),
                    artist_name=first_artist,
                    release_date=release_date,
                    album_type=album.get("album_type", "album"),
                    spotify_url=spotify_url,
                    tracked_artist_id=artist_id,
                    image_url=image_url,
                    matched_artists=[matched_name],
                    has_non_primary_match=not is_primary_match,
                    fetched_at=fetch_timestamp,
                )
            )

        next_url = payload.get("next")

    return releases


def _fetch_album_tracks(access_token: str, album_id: str) -> list[AlbumTrackItem]:
    next_url = f"{SPOTIFY_API_URL}/albums/{album_id}/tracks?{urlencode({'limit': 50})}"
    tracks: list[AlbumTrackItem] = []

    while next_url:
        payload = _spotify_request(next_url, headers={"Authorization": f"Bearer {access_token}"}, retries=1)
        items = payload.get("items", [])
        for item in items:
            track_id = item.get("id")
            if not track_id:
                continue
            artists = item.get("artists") or []
            first_artist = artists[0]["name"] if artists else "Unknown Artist"
            spotify_url = (item.get("external_urls") or {}).get("spotify")
            tracks.append(
                AlbumTrackItem(
                    id=track_id,
                    name=item.get("name", "Unknown Track"),
                    artist_name=first_artist,
                    spotify_url=spotify_url,
                    duration_ms=item.get("duration_ms"),
                )
            )
        next_url = payload.get("next")

    return tracks


def _fetch_spotify_artist(access_token: str, artist_id: str) -> SpotifyArtistItem | None:
    artist_id_clean = artist_id.strip()
    if not artist_id_clean:
        return None
    try:
        payload = _spotify_request(
            f"{SPOTIFY_API_URL}/artists/{artist_id_clean}",
            headers={"Authorization": f"Bearer {access_token}"},
            retries=1,
        )
    except HTTPException:
        return None

    name = str(payload.get("name", "")).strip()
    if not name:
        return None
    images = payload.get("images") or []
    image_url = (images[0] or {}).get("url") if images else None
    return SpotifyArtistItem(id=artist_id_clean, name=name, image_url=image_url)


def _normalize_release_range(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]:
    try:
        start_dt = (
            datetime.fromisoformat(start_date)
            if start_date
            else datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        )
        end_dt = datetime.fromisoformat(end_date) if end_date else datetime.now(UTC).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")
    return start_dt, end_dt


def _period_to_date_range(period: str) -> tuple[datetime, datetime]:
    normalized_period = period.strip().lower()
    end_dt = datetime.now(UTC).replace(tzinfo=None)
    if normalized_period == "week":
        return end_dt - timedelta(days=7), end_dt
    if normalized_period == "month":
        return end_dt - timedelta(days=30), end_dt
    if normalized_period == "year":
        return end_dt - timedelta(days=365), end_dt
    raise HTTPException(status_code=400, detail="Invalid period. Use week, month or year.")


def _read_fetch_state() -> dict[str, dict]:
    rows = _read_json_list(RELEASE_FETCH_STATE_FILE)
    state: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("key", "")).strip()
        if key:
            state[key] = row
    return state


def _write_fetch_state(state: dict[str, dict]) -> None:
    _write_json_list(RELEASE_FETCH_STATE_FILE, list(state.values()))


def _is_release_in_range(release_date: str, start_dt: datetime, end_dt: datetime) -> bool:
    try:
        normalized_date = _normalize_release_date(
            release_date,
            "day" if len(release_date) == 10 else "month" if len(release_date) == 7 else "year",
        )
    except ValueError:
        return False
    return start_dt <= normalized_date <= end_dt


def _extract_retry_after_seconds(detail: str) -> int | None:
    import re

    match = re.search(r"(\d+)s", detail)
    if not match:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    return max(value, 1)


def _merge_and_store_local_releases(new_releases: list[ReleaseItem]) -> int:
    existing_raw = _read_json_list(RELEASES_FILE)
    releases_by_id: dict[str, ReleaseItem] = {}

    for item in existing_raw:
        try:
            release = ReleaseItem(**item)
        except Exception:
            continue
        releases_by_id[release.id] = release

    for release in new_releases:
        existing = releases_by_id.get(release.id)
        if not existing:
            releases_by_id[release.id] = release
            continue

        merged_artists = sorted(set(existing.matched_artists + release.matched_artists))
        releases_by_id[release.id] = existing.model_copy(
            update={
                "matched_artists": merged_artists,
                "has_non_primary_match": existing.has_non_primary_match or release.has_non_primary_match,
                "fetched_at": release.fetched_at or existing.fetched_at,
            }
        )

    merged = sorted(releases_by_id.values(), key=lambda item: item.release_date, reverse=True)
    _write_json_list(RELEASES_FILE, [item.model_dump() for item in merged])
    return len(merged)


def _update_release_job(job_id: str, **changes: object) -> None:
    with _release_jobs_lock:
        job = _release_jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = datetime.now(UTC).isoformat()


def _update_local_fetch_job(job_id: str, **changes: object) -> None:
    with _local_fetch_jobs_lock:
        job = _local_fetch_jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = datetime.now(UTC).isoformat()


def _run_release_sync_job(job_id: str, start_dt: datetime, end_dt: datetime) -> None:
    try:
        artists = _read_json_list(ARTISTS_FILE)
        artist_ids = [str(artist.get("id", "")).strip() for artist in artists]
        artist_ids = [artist_id for artist_id in artist_ids if artist_id]
        total_artists = len(artist_ids)

        _update_release_job(job_id, status="running", total_artists=total_artists)
        if total_artists == 0:
            _update_release_job(job_id, status="completed", progress=100, releases=[])
            return

        access_token = _get_spotify_access_token()
        workers = _effective_release_workers()
        releases_by_id: dict[str, ReleaseItem] = {}
        processed = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_fetch_artist_releases, access_token, artist_id, start_dt, end_dt)
                for artist_id in artist_ids
            ]
            for future in as_completed(futures):
                try:
                    fetched_releases = future.result()
                except Exception:
                    fetched_releases = []

                for release in fetched_releases:
                    if release.id not in releases_by_id:
                        releases_by_id[release.id] = release
                processed += 1
                progress = int((processed / total_artists) * 100)
                _update_release_job(
                    job_id, processed_artists=processed, progress=max(min(progress, 100), 0)
                )

        releases = sorted(releases_by_id.values(), key=lambda item: item.release_date, reverse=True)
        _update_release_job(
            job_id,
            status="completed",
            progress=100,
            releases=[item.model_dump() for item in releases],
        )
    except Exception as exc:
        _update_release_job(job_id, status="failed", error=str(exc))


def _run_local_fetch_job(
    job_id: str, period: str, start_date: str | None = None, end_date: str | None = None
) -> None:
    import time

    try:
        artists = _read_json_list(ARTISTS_FILE)
        artist_ids = [str(artist.get("id", "")).strip() for artist in artists]
        artist_ids = [artist_id for artist_id in artist_ids if artist_id]
        total_artists = len(artist_ids)
        if start_date or end_date:
            start_dt, end_dt = _normalize_release_range(start_date, end_date)
        else:
            start_dt, end_dt = _period_to_date_range(period)
        _update_local_fetch_job(
            job_id,
            status="running",
            total_artists=total_artists,
            start_date=start_dt.date().isoformat(),
            end_date=end_dt.date().isoformat(),
        )

        if total_artists == 0:
            current_stored = len(_read_json_list(RELEASES_FILE))
            _update_local_fetch_job(
                job_id,
                status="completed",
                progress=100,
                fetched_releases=0,
                stored_releases=current_stored,
            )
            return

        access_token = _get_spotify_access_token()
        releases_by_id: dict[str, ReleaseItem] = {}
        spacing_ms = _effective_local_fetch_spacing_ms()
        processed_artists = 0

        artist_name_by_id = {
            str(item.get("id", "")).strip(): str(item.get("name", "")).strip() for item in artists
        }

        for index, artist_id in enumerate(artist_ids):
            fetched = _fetch_artist_releases(
                access_token,
                artist_id,
                start_dt,
                end_dt,
                tracked_artist_name=artist_name_by_id.get(artist_id),
            )
            for release in fetched:
                if release.id not in releases_by_id:
                    releases_by_id[release.id] = release

            processed_artists += 1
            progress = int((processed_artists / total_artists) * 100)
            _update_local_fetch_job(
                job_id,
                processed_artists=processed_artists,
                progress=max(min(progress, 100), 0),
                fetched_releases=len(releases_by_id),
            )

            if index < len(artist_ids) - 1 and spacing_ms > 0:
                time.sleep(spacing_ms / 1000)

        releases = sorted(releases_by_id.values(), key=lambda item: item.release_date, reverse=True)
        stored_count = _merge_and_store_local_releases(releases)
        _update_local_fetch_job(
            job_id,
            status="completed",
            progress=100,
            fetched_releases=len(releases),
            stored_releases=stored_count,
        )
    except Exception as exc:
        _update_local_fetch_job(job_id, status="failed", error=str(exc))


def _has_active_local_fetch_job() -> bool:
    with _local_fetch_jobs_lock:
        return any(job.get("status") in {"pending", "running"} for job in _local_fetch_jobs.values())


def _start_local_fetch_job(period: str, start_date: str | None = None, end_date: str | None = None) -> str:
    job_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    job = LocalFetchJob(
        id=job_id,
        status="pending",
        period=period,
        progress=0,
        processed_artists=0,
        total_artists=0,
        fetched_releases=0,
        stored_releases=0,
        created_at=now,
        updated_at=now,
    )
    with _local_fetch_jobs_lock:
        _local_fetch_jobs[job_id] = job.model_dump()

    Thread(
        target=_run_local_fetch_job,
        args=(job_id, period, start_date, end_date),
        daemon=True,
    ).start()
    return job_id


def _is_valid_hhmm(value: str) -> bool:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except Exception:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _auto_fetch_loop() -> None:
    import time

    while True:
        try:
            with _settings_lock:
                settings = _read_settings()

            if (
                settings.auto_fetch_enabled
                and settings.auto_fetch_window_days >= 1
                and _is_valid_hhmm(settings.auto_fetch_time)
            ):
                now = datetime.now(UTC)
                hhmm = now.strftime("%H:%M")
                today = now.date().isoformat()
                if hhmm >= settings.auto_fetch_time and settings.last_auto_fetch_date != today:
                    if not _has_active_local_fetch_job():
                        end_date = today
                        start_date = (now - timedelta(days=settings.auto_fetch_window_days)).date().isoformat()
                        _start_local_fetch_job("custom", start_date, end_date)
                        settings.last_auto_fetch_date = today
                        with _settings_lock:
                            _write_settings(settings)
        except Exception:
            # Keep scheduler resilient; next loop will retry.
            pass
        time.sleep(30)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def startup_background_tasks() -> None:
    _ensure_settings_schema()
    Thread(target=_auto_fetch_loop, daemon=True).start()


@app.get("/settings")
def get_settings() -> AppSettings:
    with _settings_lock:
        return _read_settings()


@app.put("/settings")
def update_settings(payload: AppSettingsUpdate) -> AppSettings:
    if not _is_valid_hhmm(payload.auto_fetch_time):
        raise HTTPException(status_code=400, detail="auto_fetch_time must use HH:MM (24h)")
    with _settings_lock:
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


@app.post("/settings/reverse-spotify-oauth/complete")
def complete_reverse_spotify_oauth(payload: ReverseSpotifyOAuthCompletePayload) -> dict[str, str]:
    response_url = payload.response_url.strip()
    parsed = urlparse(response_url)
    code = parse_qs(parsed.query).get("code", [""])[0].strip()
    if not code:
        raise HTTPException(status_code=400, detail="response_url must include ?code=...")

    with _settings_lock:
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


@app.get("/artistas")
def list_artists() -> list[dict]:
    return _read_json_list(ARTISTS_FILE)


@app.post("/artistas")
def create_artist(artist: ArtistCreate) -> dict:
    artists = _read_json_list(ARTISTS_FILE)

    for existing in artists:
        if existing.get("id") == artist.id:
            raise HTTPException(status_code=409, detail="Artist already exists")

    new_artist = {"id": artist.id, "name": artist.name, "image_url": artist.image_url}
    artists.append(new_artist)
    artists.sort(key=lambda item: str(item.get("name", "")).lower())
    _write_json_list(ARTISTS_FILE, artists)
    return new_artist


@app.post("/artistas/import")
def import_artists(payload: ArtistsImportPayload) -> dict:
    existing = _read_json_list(ARTISTS_FILE)
    imported = [artist.model_dump() for artist in payload.artists]

    if payload.replace:
        merged = imported
    else:
        by_id = {str(item.get("id", "")).strip(): item for item in existing if str(item.get("id", "")).strip()}
        for item in imported:
            artist_id = str(item.get("id", "")).strip()
            if not artist_id:
                continue
            by_id[artist_id] = item
        merged = list(by_id.values())

    merged.sort(key=lambda item: str(item.get("name", "")).lower())
    _write_json_list(ARTISTS_FILE, merged)
    return {"status": "ok", "total": len(merged)}


@app.delete("/artistas/{artist_id}")
def delete_artist(artist_id: str) -> dict[str, str]:
    artists = _read_json_list(ARTISTS_FILE)
    updated_artists = [item for item in artists if item.get("id") != artist_id]

    if len(updated_artists) == len(artists):
        raise HTTPException(status_code=404, detail="Artist not found")

    _write_json_list(ARTISTS_FILE, updated_artists)
    return {"status": "deleted"}


@app.post("/artistas/refresh")
def refresh_artists(only_missing_images: bool = False) -> dict:
    artists = _read_json_list(ARTISTS_FILE)
    if not artists:
        return {"status": "ok", "updated": 0, "total": 0}

    access_token = _get_spotify_access_token()
    updated = 0

    for artist in artists:
        current_id = str(artist.get("id", "")).strip()
        if not current_id:
            continue
        if only_missing_images and artist.get("image_url"):
            continue

        spotify_artist = _fetch_spotify_artist(access_token, current_id)
        if not spotify_artist:
            continue

        changed = False
        if artist.get("name") != spotify_artist.name:
            artist["name"] = spotify_artist.name
            changed = True
        if artist.get("image_url") != spotify_artist.image_url:
            artist["image_url"] = spotify_artist.image_url
            changed = True

        if changed:
            updated += 1

    artists.sort(key=lambda item: str(item.get("name", "")).lower())
    _write_json_list(ARTISTS_FILE, artists)
    return {"status": "ok", "updated": updated, "total": len(artists)}


@app.get("/spotify/artists/search")
def search_spotify_artists(q: str, limit: int = 10) -> list[SpotifyArtistItem]:
    query = q.strip()
    if len(query) < 2:
        return []

    sanitized_limit = min(max(limit, 1), 50)
    access_token = _get_spotify_access_token()
    params = urlencode({"q": query, "type": "artist", "limit": sanitized_limit})
    payload = _spotify_request(
        f"{SPOTIFY_API_URL}/search?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    items = payload.get("artists", {}).get("items", [])
    return [
        SpotifyArtistItem(
            id=item["id"],
            name=item["name"],
            image_url=((item.get("images") or [{}])[0] or {}).get("url"),
        )
        for item in items
    ]


@app.get("/spotify/albums/{album_id}/tracks")
def get_spotify_album_tracks(album_id: str) -> list[AlbumTrackItem]:
    album_id_clean = album_id.strip()
    if not album_id_clean:
        raise HTTPException(status_code=400, detail="album_id is required")
    access_token = _get_spotify_access_token()
    return _fetch_album_tracks(access_token, album_id_clean)


@app.get("/releases")
def list_releases(start_date: str | None = None, end_date: str | None = None) -> list[ReleaseItem]:
    artists = _read_json_list(ARTISTS_FILE)
    if not artists:
        return []

    try:
        start_dt = (
            datetime.fromisoformat(start_date)
            if start_date
            else datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
        )
        end_dt = datetime.fromisoformat(end_date) if end_date else datetime.now(UTC).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

    access_token = _get_spotify_access_token()
    releases_by_id: dict[str, ReleaseItem] = {}
    artist_ids = [str(artist.get("id", "")).strip() for artist in artists]
    artist_ids = [artist_id for artist_id in artist_ids if artist_id]
    workers = _effective_release_workers()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_fetch_artist_releases, access_token, artist_id, start_dt, end_dt)
            for artist_id in artist_ids
        ]

        for future in as_completed(futures):
            for release in future.result():
                if release.id not in releases_by_id:
                    releases_by_id[release.id] = release

    return sorted(releases_by_id.values(), key=lambda item: item.release_date, reverse=True)


@app.get("/releases/local")
def list_local_releases() -> list[ReleaseItem]:
    releases = _read_json_list(RELEASES_FILE)
    return [ReleaseItem(**item) for item in releases]


@app.post("/releases/local/fetch")
def fetch_local_releases(
    period: str = "month", start_date: str | None = None, end_date: str | None = None
) -> dict:
    normalized_period = period.strip().lower() if period else "month"
    if start_date or end_date:
        normalized_period = "custom"
    elif normalized_period not in {"week", "month", "year"}:
        raise HTTPException(status_code=400, detail="Invalid period. Use week, month, year or start/end date.")

    job_id = _start_local_fetch_job(normalized_period, start_date, end_date)
    return {"job_id": job_id}


@app.get("/releases/local/fetch/{job_id}")
def get_local_fetch_job(job_id: str) -> dict:
    with _local_fetch_jobs_lock:
        job = _local_fetch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local fetch job not found")
    return job


@app.get("/csv/releases")
def list_csv_releases() -> list[dict]:
    # CSV queue may contain full releases and individual track items.
    return _read_json_list(CSV_RELEASES_FILE)


@app.post("/csv/releases")
def add_csv_release(payload: CsvReleaseAddPayload) -> dict:
    release: dict | None = None
    if payload.release_id:
        release_id = payload.release_id.strip()
        if not release_id:
            raise HTTPException(status_code=400, detail="release_id is required")
        local_releases = _read_json_list(RELEASES_FILE)
        release = next((item for item in local_releases if str(item.get("id")) == release_id), None)
        if not release:
            raise HTTPException(status_code=404, detail="Release not found in local releases")
    else:
        if not payload.id or not payload.name or not payload.artist_name:
            raise HTTPException(
                status_code=400,
                detail="For custom CSV items provide id, name and artist_name.",
            )
        release = {
            "id": payload.id.strip(),
            "name": payload.name.strip(),
            "artist_name": payload.artist_name.strip(),
            "release_date": "",
            "album_type": payload.album_type.strip() or "single",
            "spotify_url": payload.spotify_url,
        }

    csv_releases = _read_json_list(CSV_RELEASES_FILE)
    if any(str(item.get("id")) == str(release.get("id")) for item in csv_releases):
        return {"status": "exists"}

    csv_releases.append(release)
    _write_json_list(CSV_RELEASES_FILE, csv_releases)
    return {"status": "added"}


@app.delete("/csv/releases/{release_id}")
def delete_csv_release(release_id: str) -> dict[str, str]:
    csv_releases = _read_json_list(CSV_RELEASES_FILE)
    updated = [item for item in csv_releases if str(item.get("id")) != release_id]
    if len(updated) == len(csv_releases):
        raise HTTPException(status_code=404, detail="Release not found in CSV list")
    _write_json_list(CSV_RELEASES_FILE, updated)
    return {"status": "deleted"}


@app.post("/artistas/{artist_id}/releases/fetch")
def fetch_artist_releases_to_local(artist_id: str, period: str = "month", force: bool = False) -> dict:
    artists = _read_json_list(ARTISTS_FILE)
    artist = next((item for item in artists if str(item.get("id")) == artist_id), None)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    start_dt, end_dt = _period_to_date_range(period)
    fetch_key = f"{artist_id}:{period}"
    fetch_state = _read_fetch_state()
    existing_releases = _read_json_list(RELEASES_FILE)
    state_row = fetch_state.get(fetch_key, {})

    if not force and state_row.get("status") == "pending":
        retry_after_seconds = int(state_row.get("retry_after_seconds", 60))
        pending_until = str(state_row.get("pending_until", ""))
        return {
            "status": "pending",
            "artist_id": artist_id,
            "artist_name": artist.get("name", "Unknown Artist"),
            "period": period,
            "retry_after_seconds": retry_after_seconds,
            "pending_until": pending_until,
            "cached": False,
        }

    if not force and fetch_key in fetch_state:
        cached = [
            item
            for item in existing_releases
            if item.get("tracked_artist_id") == artist_id
            and _is_release_in_range(str(item.get("release_date", "")), start_dt, end_dt)
        ]
        if cached:
            return {
                "status": "ok",
                "artist_id": artist_id,
                "artist_name": artist.get("name", "Unknown Artist"),
                "period": period,
                "fetched_releases": len(cached),
                "stored_releases": len(existing_releases),
                "start_date": start_dt.date().isoformat(),
                "end_date": end_dt.date().isoformat(),
                "cached": True,
            }

    access_token = _get_spotify_access_token()
    try:
        releases = _fetch_artist_releases(
            access_token,
            artist_id,
            start_dt,
            end_dt,
            tracked_artist_name=str(artist.get("name", "")),
            swallow_errors=False,
        )
    except HTTPException as exc:
        if exc.status_code == 429:
            detail = str(exc.detail)
            retry_after_seconds = _extract_retry_after_seconds(detail) or 60
            pending_until_dt = datetime.now(UTC) + timedelta(seconds=retry_after_seconds)
            fetch_state[fetch_key] = {
                "key": fetch_key,
                "artist_id": artist_id,
                "period": period,
                "status": "pending",
                "pending_until": pending_until_dt.isoformat(),
                "retry_after_seconds": retry_after_seconds,
                "last_error": detail,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            _write_fetch_state(fetch_state)
            return {
                "status": "pending",
                "artist_id": artist_id,
                "artist_name": artist.get("name", "Unknown Artist"),
                "period": period,
                "retry_after_seconds": retry_after_seconds,
                "pending_until": pending_until_dt.isoformat(),
                "cached": False,
            }
        raise
    stored_count = _merge_and_store_local_releases(releases)
    fetch_state[fetch_key] = {
        "key": fetch_key,
        "artist_id": artist_id,
        "period": period,
        "status": "ready",
        "start_date": start_dt.date().isoformat(),
        "end_date": end_dt.date().isoformat(),
        "fetched_at": datetime.now(UTC).isoformat(),
        "release_count": len(releases),
    }
    _write_fetch_state(fetch_state)
    return {
        "status": "ok",
        "artist_id": artist_id,
        "artist_name": artist.get("name", "Unknown Artist"),
        "period": period,
        "fetched_releases": len(releases),
        "stored_releases": stored_count,
        "start_date": start_dt.date().isoformat(),
        "end_date": end_dt.date().isoformat(),
        "cached": False,
    }


@app.post("/releases/sync")
def start_releases_sync(start_date: str | None = None, end_date: str | None = None) -> dict[str, str]:
    start_dt, end_dt = _normalize_release_range(start_date, end_date)
    job_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    job = ReleaseSyncJob(
        id=job_id,
        status="pending",
        progress=0,
        processed_artists=0,
        total_artists=0,
        start_date=start_dt.date().isoformat(),
        end_date=end_dt.date().isoformat(),
        created_at=now,
        updated_at=now,
    )

    with _release_jobs_lock:
        _release_jobs[job_id] = job.model_dump()

    Thread(target=_run_release_sync_job, args=(job_id, start_dt, end_dt), daemon=True).start()
    return {"job_id": job_id}


@app.get("/releases/sync/{job_id}")
def get_releases_sync(job_id: str) -> dict:
    with _release_jobs_lock:
        job = _release_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Release sync job not found")
    return job


@app.get("/erros")
def list_errors() -> list[dict]:
    return _read_json_list(ERRORS_FILE)


@app.post("/erros")
def create_error(error: SyncErrorCreate) -> SyncErrorItem:
    errors = _read_json_list(ERRORS_FILE)
    normalized_artist = error.artist_name.strip().lower()
    normalized_track = error.track_name.strip().lower()

    for index, item in enumerate(errors):
        current_artist = str(item.get("artist_name", "")).strip().lower()
        current_track = str(item.get("track_name", "")).strip().lower()
        if current_artist != normalized_artist or current_track != normalized_track:
            continue

        updated_item = dict(item)
        updated_item["reason"] = error.reason
        updated_item["album_name"] = error.album_name
        if not str(updated_item.get("spotify_url_manual", "")).strip():
            updated_item["spotify_url_manual"] = error.spotify_url_manual
        if not str(updated_item.get("tidal_url_manual", "")).strip():
            updated_item["tidal_url_manual"] = error.tidal_url_manual
        current_attempts = int(updated_item.get("attempts", 1) or 1)
        updated_item["attempts"] = max(current_attempts + 1, 1)
        errors[index] = updated_item
        _write_json_list(ERRORS_FILE, errors)
        return SyncErrorItem(**updated_item)

    new_error = SyncErrorItem(
        id=str(uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        attempts=1,
        **error.model_dump(),
    )
    errors.append(new_error.model_dump())
    _write_json_list(ERRORS_FILE, errors)
    return new_error


@app.delete("/erros/{error_id}")
def delete_error(error_id: str) -> dict[str, str]:
    errors = _read_json_list(ERRORS_FILE)
    updated_errors = [item for item in errors if item.get("id") != error_id]

    if len(updated_errors) == len(errors):
        raise HTTPException(status_code=404, detail="Error not found")

    _write_json_list(ERRORS_FILE, updated_errors)
    return {"status": "deleted"}


@app.put("/erros/{error_id}/links")
def update_error_links(error_id: str, payload: SyncErrorLinksUpdate) -> SyncErrorItem:
    errors = _read_json_list(ERRORS_FILE)
    for index, item in enumerate(errors):
        if item.get("id") != error_id:
            continue

        updated_item = dict(item)
        updated_item["spotify_url_manual"] = (
            payload.spotify_url_manual.strip() if payload.spotify_url_manual else None
        )
        updated_item["tidal_url_manual"] = (
            payload.tidal_url_manual.strip() if payload.tidal_url_manual else None
        )
        errors[index] = updated_item
        _write_json_list(ERRORS_FILE, errors)
        return SyncErrorItem(**updated_item)

    raise HTTPException(status_code=404, detail="Error not found")


@app.post("/settings/ytmusic-auth/import")
def import_ytmusic_auth(payload: YTMusicAuthImportPayload) -> dict[str, str]:
    targets = _ytmusic_auth_targets()

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(json.dumps(payload.auth_json, ensure_ascii=True, indent=2) + "\n")
        except PermissionError as exc:
            raise HTTPException(status_code=500, detail=f"No write permission to {target}") from exc

    return {"status": "ok", "updated_files": ", ".join(str(item) for item in targets)}


@app.post("/settings/ytmusic-auth/validate")
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


@app.get("/historico")
def list_historico() -> list[dict]:
    return _read_json_list(HISTORICO_FILE)


@app.post("/historico")
def create_historico(item: HistoricoItem) -> dict:
    historico = _read_json_list(HISTORICO_FILE)
    if any(str(existing.get("id")) == item.id for existing in historico):
        return {"status": "exists"}
    payload = item.model_dump()
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(UTC).isoformat()
    historico.append(payload)
    _write_json_list(HISTORICO_FILE, historico)
    return {"status": "added"}
