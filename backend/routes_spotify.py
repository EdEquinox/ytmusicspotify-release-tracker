from __future__ import annotations

import os
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException

from config import SPOTIFY_API_URL
import state
from releases_service import _fetch_album_tracks
from schemas import AlbumTrackItem, SpotifyArtistItem, SpotifySpotiflacDownloadPayload
from settings_service import _effective_spotify_market, _read_settings
from spotify_api import _get_spotify_access_token, _spotify_request
from spotiflac_runner import _download_with_spotiflac, _normalize_spotiflac_template

router = APIRouter(tags=["spotify"])


def _parse_spotify_track_url(url: str) -> tuple[str, str]:
    raw = url.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="spotify_url is required")
    if raw.startswith("spotify:track:"):
        track_id = raw.split("spotify:track:", 1)[1].split("?", 1)[0].strip()
        if not track_id:
            raise HTTPException(status_code=400, detail="Invalid spotify:track: URL")
        return f"https://open.spotify.com/track/{track_id}", track_id
    if "open.spotify.com/track/" in raw:
        tail = raw.split("open.spotify.com/track/", 1)[1]
        track_id = tail.split("?", 1)[0].split("/", 1)[0].strip()
        if not track_id:
            raise HTTPException(status_code=400, detail="Invalid open.spotify.com track URL")
        return f"https://open.spotify.com/track/{track_id}", track_id
    raise HTTPException(
        status_code=400,
        detail="Use a Spotify track URL (https://open.spotify.com/track/... ou spotify:track:...)",
    )


@router.get("/spotify/artists/search")
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


@router.get("/spotify/tracks/search")
def search_spotify_tracks(q: str, limit: int = 15) -> list[AlbumTrackItem]:
    query = q.strip()
    if len(query) < 2:
        return []

    sanitized_limit = min(max(limit, 1), 50)
    access_token = _get_spotify_access_token()
    params_dict: dict[str, str | int] = {"q": query, "type": "track", "limit": sanitized_limit}
    market = _effective_spotify_market()
    if market:
        params_dict["market"] = market
    params = urlencode(params_dict)
    payload = _spotify_request(
        f"{SPOTIFY_API_URL}/search?{params}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    items = payload.get("tracks", {}).get("items", [])
    results: list[AlbumTrackItem] = []
    for item in items:
        track_id = item.get("id")
        if not track_id:
            continue
        artists = item.get("artists") or []
        first_artist = artists[0]["name"] if artists else "Unknown Artist"
        spotify_url = (item.get("external_urls") or {}).get("spotify")
        results.append(
            AlbumTrackItem(
                id=track_id,
                name=item.get("name", "Unknown Track"),
                artist_name=first_artist,
                spotify_url=spotify_url,
                duration_ms=item.get("duration_ms"),
            )
        )
    return results


@router.get("/spotify/albums/{album_id}/tracks")
def get_spotify_album_tracks(album_id: str) -> list[AlbumTrackItem]:
    album_id_clean = album_id.strip()
    if not album_id_clean:
        raise HTTPException(status_code=400, detail="album_id is required")
    access_token = _get_spotify_access_token()
    return _fetch_album_tracks(access_token, album_id_clean)


def _track_meta_for_spotiflac(access_token: str, track_id: str) -> tuple[str, str, list[str], list[str]]:
    payload = _spotify_request(
        f"{SPOTIFY_API_URL}/tracks/{track_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        retries=1,
    )
    title = str(payload.get("name", "Unknown")).strip() or "Unknown"
    artists_list = [str(a.get("name", "")).strip() for a in (payload.get("artists") or []) if a.get("name")]
    primary = artists_list[0] if artists_list else "Unknown"
    album_artists_raw = [str(a.get("name", "")).strip() for a in (payload.get("album", {}) or {}).get("artists", []) or [] if a.get("name")]
    if album_artists_raw:
        album_artists = [album_artists_raw[0]]
    else:
        album_artists = [primary]
    spotify_artists = artists_list if artists_list else [primary]
    return title, primary, spotify_artists, album_artists


@router.post("/spotify/spotiflac-download")
def spotiflac_download_track(payload: SpotifySpotiflacDownloadPayload) -> dict[str, str | bool]:
    canonical_url, track_id = _parse_spotify_track_url(payload.spotify_url)
    access_token = _get_spotify_access_token()
    title, primary_artist, spotify_artists_list, spotify_album_artists_list = _track_meta_for_spotiflac(
        access_token, track_id
    )

    with state._settings_lock:
        settings = _read_settings()

    output_dir = (settings.reverse_spotiflac_output_dir or "/data/downloads").strip() or "/data/downloads"
    command_template = _normalize_spotiflac_template(settings.reverse_spotiflac_command_template)
    timeout_seconds = max(int(settings.reverse_spotiflac_timeout_seconds or 600), 10)
    loop_minutes = max(int(settings.reverse_spotiflac_loop_minutes or 0), 0)

    filename_format = (
        os.getenv("REVERSE_SPOTIFLAC_FILENAME_FORMAT", "{title} - {artist}").strip() or "{title} - {artist}"
    )
    use_artist_subfolders = os.getenv("REVERSE_SPOTIFLAC_USE_ARTIST_SUBFOLDERS", "true").strip().lower() != "false"
    use_album_subfolders = os.getenv("REVERSE_SPOTIFLAC_USE_ALBUM_SUBFOLDERS", "true").strip().lower() != "false"
    services = ["tidal"]

    ok, detail = _download_with_spotiflac(
        spotify_url=canonical_url,
        artist=primary_artist,
        title=title,
        output_dir=output_dir,
        command_template=command_template,
        timeout_seconds=timeout_seconds,
        services=services,
        filename_format=filename_format,
        use_artist_subfolders=use_artist_subfolders,
        use_album_subfolders=use_album_subfolders,
        loop_minutes=loop_minutes,
        spotify_artists_list=spotify_artists_list,
        spotify_album_artists_list=spotify_album_artists_list,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=detail)
    return {"ok": True, "message": detail or "Download concluido.", "output_dir": output_dir}
