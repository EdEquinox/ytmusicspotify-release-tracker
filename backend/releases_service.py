from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import HTTPException

from config import RELEASE_FETCH_STATE_FILE, RELEASES_FILE, SPOTIFY_API_URL
from json_io import _read_json_list, _write_json_list
from schemas import AlbumTrackItem, ReleaseItem, SpotifyArtistItem
from settings_service import _effective_include_groups, _effective_spotify_market
from spotify_api import _spotify_request


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
    state_map: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("key", "")).strip()
        if key:
            state_map[key] = row
    return state_map


def _write_fetch_state(state_map: dict[str, dict]) -> None:
    _write_json_list(RELEASE_FETCH_STATE_FILE, list(state_map.values()))


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
