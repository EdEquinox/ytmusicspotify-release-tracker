from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from threading import Thread
from uuid import uuid4

from config import ARTISTS_FILE, RELEASES_FILE
from json_io import _read_json_list
from releases_service import (
    _fetch_artist_releases,
    _merge_and_store_local_releases,
    _normalize_release_range,
    _period_to_date_range,
)
from schemas import LocalFetchJob, ReleaseItem, ReleaseSyncJob
import state
from settings_service import (
    _effective_local_fetch_spacing_ms,
    _effective_release_workers,
    _read_settings,
    _write_settings,
)
from spotify_api import _get_spotify_access_token


def _update_release_job(job_id: str, **changes: object) -> None:
    with state._release_jobs_lock:
        job = state._release_jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = datetime.now(UTC).isoformat()


def _update_local_fetch_job(job_id: str, **changes: object) -> None:
    with state._local_fetch_jobs_lock:
        job = state._local_fetch_jobs.get(job_id)
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
    with state._local_fetch_jobs_lock:
        return any(job.get("status") in {"pending", "running"} for job in state._local_fetch_jobs.values())


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
    with state._local_fetch_jobs_lock:
        state._local_fetch_jobs[job_id] = job.model_dump()

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
    while True:
        try:
            with state._settings_lock:
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
                        with state._settings_lock:
                            _write_settings(settings)
        except Exception:
            pass
        time.sleep(30)
