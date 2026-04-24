from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config import ARTISTS_FILE
from json_io import _read_json_list, _write_json_list
from schemas import ArtistCreate, ArtistsImportPayload
from releases_service import _fetch_spotify_artist
from spotify_api import _get_spotify_access_token

router = APIRouter(tags=["artists"])


@router.get("/artistas")
def list_artists() -> list[dict]:
    return _read_json_list(ARTISTS_FILE)


@router.post("/artistas")
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


@router.post("/artistas/import")
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


@router.delete("/artistas/{artist_id}")
def delete_artist(artist_id: str) -> dict[str, str]:
    artists = _read_json_list(ARTISTS_FILE)
    updated_artists = [item for item in artists if item.get("id") != artist_id]

    if len(updated_artists) == len(artists):
        raise HTTPException(status_code=404, detail="Artist not found")

    _write_json_list(ARTISTS_FILE, updated_artists)
    return {"status": "deleted"}


@router.post("/artistas/refresh")
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
