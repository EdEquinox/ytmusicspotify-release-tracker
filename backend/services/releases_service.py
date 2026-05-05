from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from fastapi import HTTPException

from core.config import RELEASE_FETCH_STATE_FILE, RELEASES_FILE
from core.json_io import _read_json_list, _write_json_list
from models.schemas import AlbumTrackItem, ReleaseItem


def _normalize_release_date(date_value: str, precision: str) -> datetime:
    if precision == "year":
        return datetime.fromisoformat(f"{date_value}-01-01")
    if precision == "month":
        return datetime.fromisoformat(f"{date_value}-01")
    return datetime.fromisoformat(date_value)


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


def _tidal_album_cover_url(album: Any) -> str | None:
    """URL da capa (Tidal CDN). Requer ``album.cover`` preenchido pelo parse da API."""
    try:
        if not getattr(album, "cover", None):
            return None
        url = album.image(640)
        return str(url).strip() or None
    except Exception:
        return None


def _tidal_album_release_date_str(album: Any) -> str | None:
    rd = getattr(album, "release_date", None) or getattr(album, "available_release_date", None)
    if rd is None:
        return None
    if isinstance(rd, datetime):
        return rd.strftime("%Y-%m-%d")
    if isinstance(rd, str):
        return rd.split("T")[0][:10]
    return None


def _spotify_id_for_artist(artist: dict) -> str:
    """ID Spotify (base62). Se existir a chave ``spotify_id`` no JSON (mesmo vazia), não usar ``id`` como Spotify."""
    if "spotify_id" in artist:
        return str(artist.get("spotify_id") or "").strip()
    return str(artist.get("id") or "").strip()


def _tidal_numeric_id_for_artist(artist: dict) -> str | None:
    """ID numérico Tidal. Formato legado: ``id`` só dígitos quando existe ``spotify_id``."""
    explicit = str(artist.get("tidal_id") or "").strip()
    if explicit:
        return explicit
    sid = str(artist.get("spotify_id") or "").strip()
    id_field = str(artist.get("id") or "").strip()
    if sid and id_field.isdigit():
        return id_field
    return None


def _tracked_artist_id_for_releases(artist: dict) -> str:
    """Valor gravado em ``ReleaseItem.tracked_artist_id``: Spotify se existir, senão ID Tidal numérico."""
    sid = _spotify_id_for_artist(artist)
    if sid:
        return sid
    tid = _tidal_numeric_id_for_artist(artist)
    return str(tid or "").strip()


def _artist_matches_route_id(artist: dict, artist_id: str) -> bool:
    """``/artistas/{id}`` pode usar Spotify id ou, no legado, o id Tidal guardado em ``id``."""
    needle = str(artist_id).strip()
    if not needle:
        return False
    if str(artist.get("id", "")).strip() == needle:
        return True
    if str(artist.get("spotify_id", "")).strip() == needle:
        return True
    return False


def _fetch_artist_releases_tidal(
    session: Any,
    tidal_artist_id: str,
    tracked_artist_id: str,
    tracked_artist_name: str,
    start_dt: datetime,
    end_dt: datetime,
    swallow_errors: bool = True,
) -> list[ReleaseItem]:
    """Catálogo Tidal (v1) — três gavetas como ``testtidal_original.py``.

    ``tracked_artist_id`` costumava ser só Spotify; com fluxo Tidal-only usa-se o ID Tidal
    quando não há ``spotify_id`` no JSON de artistas.
    """

    releases: list[ReleaseItem] = []
    seen_ids: set[str] = set()
    fetch_timestamp = datetime.now(UTC).isoformat()

    try:
        artista = session.artist(int(tidal_artist_id))
    except Exception:
        if swallow_errors:
            return releases
        raise

    gavetas: list[tuple[list[Any], str]] = [
        (artista.get_albums(), "album"),
        (artista.get_ep_singles(), "single"),
        (artista.get_other(), "compilation"),
    ]

    for lista_albums, album_type in gavetas:
        for album in lista_albums:
            aid = getattr(album, "id", None)
            if aid is None:
                continue
            sid = str(int(aid))
            if sid in seen_ids:
                continue

            titulo = getattr(album, "name", None) or ""
            if not titulo:
                continue

            rds = _tidal_album_release_date_str(album)
            if not rds:
                continue
            try:
                normalized = datetime.strptime(rds[:10], "%Y-%m-%d")
            except ValueError:
                continue
            if normalized < start_dt or normalized > end_dt:
                continue

            seen_ids.add(sid)
            artists_list = getattr(album, "artists", None) or []
            first = artists_list[0] if artists_list else None
            first_name = getattr(first, "name", None) or "Unknown Artist"
            first_id = str(int(getattr(first, "id", 0))) if first and getattr(first, "id", None) else None
            is_primary = (
                True if not first_id else (first_id == str(int(tidal_artist_id)))
            )
            tidal_link = getattr(album, "share_url", None) or getattr(album, "listen_url", None) or ""
            cover_url = _tidal_album_cover_url(album)

            releases.append(
                ReleaseItem(
                    id=sid,
                    name=str(titulo),
                    artist_name=str(first_name),
                    release_date=rds[:10],
                    album_type=album_type,
                    spotify_url=None,
                    tidal_url=tidal_link or None,
                    source="tidal",
                    tracked_artist_id=tracked_artist_id,
                    image_url=cover_url,
                    matched_artists=[tracked_artist_name or str(first_name)],
                    has_non_primary_match=not is_primary,
                    fetched_at=fetch_timestamp,
                )
            )

    return releases


def _fetch_tidal_album_tracks(session: Any, album_id: str) -> list[AlbumTrackItem]:
    from tidalapi.album import Album

    album_id_clean = album_id.strip()
    if not album_id_clean:
        return []
    al = Album(session, album_id_clean)
    out: list[AlbumTrackItem] = []
    for tr in al.tracks():
        tid = getattr(tr, "id", None)
        if tid is None:
            continue
        artists_list = getattr(tr, "artists", None) or []
        first = artists_list[0] if artists_list else getattr(tr, "artist", None)
        an = getattr(first, "name", None) if first else "Unknown Artist"
        dur_s = getattr(tr, "duration", None)
        dur_ms = int(dur_s * 1000) if isinstance(dur_s, (int, float)) else None
        share = getattr(tr, "share_url", None) or getattr(tr, "listen_url", None)
        out.append(
            AlbumTrackItem(
                id=str(int(tid)),
                name=str(getattr(tr, "name", None) or getattr(tr, "title", "") or "Unknown Track"),
                artist_name=str(an or "Unknown Artist"),
                spotify_url=None,
                tidal_url=share or None,
                duration_ms=dur_ms,
            )
        )
    return out


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
        new_cover = release.image_url or existing.image_url
        releases_by_id[release.id] = existing.model_copy(
            update={
                "matched_artists": merged_artists,
                "has_non_primary_match": existing.has_non_primary_match or release.has_non_primary_match,
                "fetched_at": release.fetched_at or existing.fetched_at,
                "image_url": new_cover,
            }
        )

    merged = sorted(releases_by_id.values(), key=lambda item: item.release_date, reverse=True)
    _write_json_list(RELEASES_FILE, [item.model_dump() for item in merged])
    return len(merged)
