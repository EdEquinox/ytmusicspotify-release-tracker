from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from threading import Thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from config import ARTISTS_FILE, CSV_RELEASES_FILE, RELEASES_FILE
from json_io import _read_json_list, _write_json_list
from jobs_service import _run_release_sync_job, _start_local_fetch_job
from schemas import CsvReleaseAddPayload, ReleaseItem, ReleaseSyncJob
import state
from releases_service import (
    _extract_retry_after_seconds,
    _fetch_artist_releases,
    _is_release_in_range,
    _merge_and_store_local_releases,
    _normalize_release_range,
    _period_to_date_range,
    _read_fetch_state,
    _write_fetch_state,
)
from settings_service import _effective_release_workers
from spotify_api import _get_spotify_access_token

router = APIRouter(tags=["releases"])


@router.get("/releases")
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


@router.get("/releases/local")
def list_local_releases() -> list[ReleaseItem]:
    releases = _read_json_list(RELEASES_FILE)
    return [ReleaseItem(**item) for item in releases]


@router.post("/releases/local/fetch")
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


@router.get("/releases/local/fetch/{job_id}")
def get_local_fetch_job(job_id: str) -> dict:
    with state._local_fetch_jobs_lock:
        job = state._local_fetch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Local fetch job not found")
    return job


@router.get("/csv/releases")
def list_csv_releases() -> list[dict]:
    return _read_json_list(CSV_RELEASES_FILE)


@router.post("/csv/releases")
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


@router.delete("/csv/releases/{release_id}")
def delete_csv_release(release_id: str) -> dict[str, str]:
    csv_releases = _read_json_list(CSV_RELEASES_FILE)
    updated = [item for item in csv_releases if str(item.get("id")) != release_id]
    if len(updated) == len(csv_releases):
        raise HTTPException(status_code=404, detail="Release not found in CSV list")
    _write_json_list(CSV_RELEASES_FILE, updated)
    return {"status": "deleted"}


@router.post("/artistas/{artist_id}/releases/fetch")
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


@router.post("/releases/sync")
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

    with state._release_jobs_lock:
        state._release_jobs[job_id] = job.model_dump()

    Thread(target=_run_release_sync_job, args=(job_id, start_dt, end_dt), daemon=True).start()
    return {"job_id": job_id}


@router.get("/releases/sync/{job_id}")
def get_releases_sync(job_id: str) -> dict:
    with state._release_jobs_lock:
        job = state._release_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Release sync job not found")
    return job
