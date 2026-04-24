from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from config import CSV_RELEASES_FILE, ERRORS_FILE
from json_io import _read_json_list, _write_json_list
from schemas import SyncErrorCreate, SyncErrorItem, SyncErrorLinksUpdate

router = APIRouter(tags=["errors"])


@router.get("/erros")
def list_errors() -> list[dict]:
    return _read_json_list(ERRORS_FILE)


@router.post("/erros")
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
        updated_item["clear_csv_on_resolve"] = error.clear_csv_on_resolve
        rid = (error.release_id or "").strip()
        if rid:
            updated_item["release_id"] = rid
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


@router.post("/erros/{error_id}/resolve")
def resolve_error(error_id: str) -> dict[str, str | bool]:
    errors = _read_json_list(ERRORS_FILE)
    removed: dict | None = None
    for item in errors:
        if item.get("id") == error_id:
            removed = item
            break
    if not removed:
        raise HTTPException(status_code=404, detail="Error not found")

    updated_errors = [item for item in errors if item.get("id") != error_id]
    _write_json_list(ERRORS_FILE, updated_errors)

    csv_removed = False
    if removed.get("clear_csv_on_resolve") and (removed.get("release_id") or "").strip():
        rid = str(removed.get("release_id")).strip()
        csv_releases = _read_json_list(CSV_RELEASES_FILE)
        csv_next = [row for row in csv_releases if str(row.get("id")) != rid]
        if len(csv_next) != len(csv_releases):
            _write_json_list(CSV_RELEASES_FILE, csv_next)
            csv_removed = True

    return {"status": "resolved", "csv_removed": csv_removed}


@router.delete("/erros/{error_id}")
def delete_error(error_id: str) -> dict[str, str]:
    errors = _read_json_list(ERRORS_FILE)
    updated_errors = [item for item in errors if item.get("id") != error_id]

    if len(updated_errors) == len(errors):
        raise HTTPException(status_code=404, detail="Error not found")

    _write_json_list(ERRORS_FILE, updated_errors)
    return {"status": "deleted"}


@router.put("/erros/{error_id}/links")
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
