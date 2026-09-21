"""HTTP-adjacent orchestration for release endpoints (called from routes)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from threading import Thread
from uuid import uuid4

from fastapi import HTTPException

from core import state
from core.config import ARTISTS_FILE, CSV_RELEASES_FILE, PLAYLIST_TRACK_LINKS_FILE, RELEASES_FILE
from core.json_io import _read_json_list, _write_json_list
from models.schemas import (
    AlbumTrackItem,
    CsvReleaseAddPayload,
    PlaylistTrackLinksUpsertPayload,
    ReleaseItem,
    ReleaseSyncJob,
    SpotifyArtistItem,
)
from services.jobs_service import _run_release_sync_job, _start_local_fetch_job
from services.releases_service import (
    _artist_matches_route_id,
    _fetch_artist_releases_tidal,
    _fetch_tidal_album_tracks,
    _is_release_in_range,
    _merge_and_store_local_releases,
    _normalize_release_range,
    _period_to_date_range,
    _read_fetch_state,
    _tidal_numeric_id_for_artist,
    _tracked_artist_id_for_releases,
    _write_fetch_state,
)
from services.settings_service import _effective_release_workers, _read_settings
from services.tidal_auth_service import (
    get_tidal_device_login_status,
    load_tidal_session,
    start_tidal_device_login,
    tidal_session_logged_in,
)


def list_releases_catalog(start_date: str | None, end_date: str | None) -> list[ReleaseItem]:
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

    session = load_tidal_session()
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Sessão Tidal em falta. Na página Releases, inicia login Tidal antes de listar o catálogo.",
        )

    releases_by_id: dict[str, ReleaseItem] = {}
    workers = _effective_release_workers()
    tasks: list[tuple[str, str, str]] = []
    for artist in artists:
        tidal_id = _tidal_numeric_id_for_artist(artist)
        if not tidal_id:
            continue
        tracked = _tracked_artist_id_for_releases(artist)
        if not tracked:
            continue
        name = str(artist.get("name", "")).strip()
        tasks.append((tidal_id, tracked, name))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _fetch_artist_releases_tidal,
                session,
                tidal_id,
                tracked_id,
                name,
                start_dt,
                end_dt,
            )
            for tidal_id, tracked_id, name in tasks
        ]

        for future in as_completed(futures):
            for release in future.result():
                if release.id not in releases_by_id:
                    releases_by_id[release.id] = release

    return sorted(releases_by_id.values(), key=lambda item: item.release_date, reverse=True)


def list_local_releases_from_disk() -> list[ReleaseItem]:
    releases = _read_json_list(RELEASES_FILE)
    return [ReleaseItem(**item) for item in releases]


def delete_local_releases_by_fetched_day(fetched_day: str) -> dict[str, int | str]:
    """Remove local catalog releases whose fetched_at date matches ``fetched_day`` (YYYY-MM-DD).

    Use ``sem-fetch-day`` to delete releases without a usable fetched_at day.
    """
    day = (fetched_day or "").strip()
    if not day:
        raise HTTPException(status_code=400, detail="fetched_day is required")

    releases = _read_json_list(RELEASES_FILE)
    kept: list[dict] = []
    removed = 0
    for item in releases:
        fetched_at = str(item.get("fetched_at") or "").strip()
        item_day = fetched_at[:10] if fetched_at else "sem-fetch-day"
        if item_day == day:
            removed += 1
        else:
            kept.append(item)

    if removed == 0:
        raise HTTPException(status_code=404, detail=f"No releases found for fetch day {day}")

    _write_json_list(RELEASES_FILE, kept)
    return {"deleted": removed, "fetched_day": day, "remaining": len(kept)}


def start_fetch_local_job(period: str, start_date: str | None, end_date: str | None) -> dict:
    normalized_period = period.strip().lower() if period else "month"
    if start_date or end_date:
        normalized_period = "custom"
    elif normalized_period not in {"week", "month", "year"}:
        raise HTTPException(status_code=400, detail="Invalid period. Use week, month, year or start/end date.")

    job_id = _start_local_fetch_job(normalized_period, start_date, end_date)
    return {"job_id": job_id}


def get_local_fetch_job(job_id: str) -> dict:
    with state._local_fetch_jobs_lock:
        job = state._local_fetch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local fetch job not found")
    return job


def list_csv_releases() -> list[dict]:
    return _read_json_list(CSV_RELEASES_FILE)


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
            "tidal_url": payload.tidal_url,
        }

    csv_releases = _read_json_list(CSV_RELEASES_FILE)
    if any(str(item.get("id")) == str(release.get("id")) for item in csv_releases):
        return {"status": "exists"}

    csv_releases.append(release)
    _write_json_list(CSV_RELEASES_FILE, csv_releases)
    return {"status": "added"}


def delete_csv_release(release_id: str) -> dict[str, str]:
    csv_releases = _read_json_list(CSV_RELEASES_FILE)
    updated = [item for item in csv_releases if str(item.get("id")) != release_id]
    if len(updated) == len(csv_releases):
        raise HTTPException(status_code=404, detail="Release not found in CSV list")
    _write_json_list(CSV_RELEASES_FILE, updated)
    return {"status": "deleted"}


def list_playlist_track_links() -> list[dict]:
    return _read_json_list(PLAYLIST_TRACK_LINKS_FILE)


def upsert_playlist_track_links(payload: PlaylistTrackLinksUpsertPayload) -> dict[str, int | str]:
    rows = _read_json_list(PLAYLIST_TRACK_LINKS_FILE)
    by_video: dict[str, dict] = {}
    for row in rows:
        vid = str(row.get("yt_video_id", "")).strip()
        if vid:
            by_video[vid] = dict(row)

    now = datetime.now(UTC).isoformat()
    merged = 0
    for item in payload.items:
        vid = item.yt_video_id.strip()
        if not vid:
            continue
        prev = by_video.get(vid, {})
        entry: dict = {
            "yt_video_id": vid,
            "tidal_url": (item.tidal_url or "").strip() or None,
            "release_id": (item.release_id or "").strip() or None,
            "artist_name": (item.artist_name or "").strip(),
            "release_name": (item.release_name or "").strip(),
            "updated_at": now,
        }
        entry["created_at"] = prev.get("created_at") or now
        by_video[vid] = entry
        merged += 1

    _write_json_list(PLAYLIST_TRACK_LINKS_FILE, list(by_video.values()))
    return {"status": "ok", "upserted": merged}


def fetch_artist_releases_to_local(artist_id: str, period: str, force: bool) -> dict:
    artists = _read_json_list(ARTISTS_FILE)
    artist = next((item for item in artists if _artist_matches_route_id(item, artist_id)), None)
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

    tidal_id = _tidal_numeric_id_for_artist(artist)
    if not tidal_id:
        raise HTTPException(
            status_code=400,
            detail="Sem ID Tidal para este artista: em formato legado usa o número em «id» com «spotify_id»; no novo formato define «tidal_id» em Gerir Artistas.",
        )

    session = load_tidal_session()
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Sessão Tidal em falta. Na página Releases, inicia login Tidal (link no popup) e tenta de novo.",
        )

    try:
        releases = _fetch_artist_releases_tidal(
            session,
            tidal_id,
            artist_id,
            str(artist.get("name", "")),
            start_dt,
            end_dt,
            swallow_errors=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao obter releases no Tidal: {exc}") from exc
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


def start_releases_sync(start_date: str | None, end_date: str | None) -> dict[str, str]:
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

    with state._release_jobs_lock:
        state._release_jobs[job_id] = job.model_dump()

    Thread(target=_run_release_sync_job, args=(job_id, start_dt, end_dt), daemon=True).start()
    return {"job_id": job_id}


def get_releases_sync(job_id: str) -> dict:
    with state._release_jobs_lock:
        job = state._release_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Release sync job not found")
    return job


def tidal_session_status() -> dict[str, bool]:
    return {"logged_in": tidal_session_logged_in()}


def tidal_device_start() -> dict:
    return start_tidal_device_login()


def tidal_device_status() -> dict:
    return get_tidal_device_login_status()


def tidal_album_tracks(album_id: str) -> list[AlbumTrackItem]:
    session = load_tidal_session()
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Sessão Tidal em falta. Completa o login Tidal na página Releases.",
        )
    return _fetch_tidal_album_tracks(session, album_id)


def search_tidal_artists(q: str, limit: int = 15) -> list[SpotifyArtistItem]:
    from tidalapi.artist import Artist as TidalArtist

    query = (q or "").strip()
    if len(query) < 2:
        return []
    session = load_tidal_session()
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Sessão Tidal em falta. Completa o login Tidal (página Releases) antes de pesquisar artistas.",
        )
    lim = min(max(int(limit or 15), 1), 50)
    try:
        raw = session.search(query, models=[TidalArtist], limit=lim, offset=0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pesquisa Tidal falhou: {exc}") from exc

    items = raw.get("artists") or []
    out: list[SpotifyArtistItem] = []
    for ar in items:
        aid = getattr(ar, "id", None)
        if aid is None:
            continue
        name = str(getattr(ar, "name", None) or "").strip()
        if not name:
            continue
        image_url = ar.image()
        if getattr(ar, "picture", None) and ar.picture is not None and callable(getattr(ar, "picture")):
            image_url = ar.picture(640)

        out.append(SpotifyArtistItem(id=str(int(aid)), name=name, image_url=image_url))
    return out


def search_tidal_tracks(q: str, limit: int = 15) -> list[AlbumTrackItem]:
    from tidalapi.media import Track

    query = (q or "").strip()
    if len(query) < 2:
        return []
    session = load_tidal_session()
    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Sessão Tidal em falta. Completa o login Tidal antes de pesquisar faixas.",
        )
    lim = min(max(int(limit or 15), 1), 50)
    try:
        raw = session.search(query, models=[Track], limit=lim, offset=0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pesquisa Tidal falhou: {exc}") from exc

    tracks = raw.get("tracks") or []
    out: list[AlbumTrackItem] = []
    for tr in tracks:
        tid = getattr(tr, "id", None)
        if tid is None:
            continue
        artists_list = getattr(tr, "artists", None) or []
        first = artists_list[0] if artists_list else getattr(tr, "artist", None)
        an = getattr(first, "name", None) if first else None
        title = (
            str(getattr(tr, "full_name", None) or getattr(tr, "name", None) or getattr(tr, "title", "") or "")
            .strip()
            or "Unknown Track"
        )
        dur_s = getattr(tr, "duration", None)
        dur_ms = int(float(dur_s) * 1000) if isinstance(dur_s, (int, float)) else None
        share = getattr(tr, "share_url", None) or getattr(tr, "listen_url", None)
        out.append(
            AlbumTrackItem(
                id=str(int(tid)),
                name=title,
                artist_name=str(an or "Unknown Artist"),
                spotify_url=None,
                tidal_url=str(share).strip() if share else None,
                duration_ms=dur_ms,
            )
        )
    return out
