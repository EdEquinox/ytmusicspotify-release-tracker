from __future__ import annotations

from fastapi import APIRouter, HTTPException

from core.config import ARTISTS_FILE
from core.json_io import _read_json_list, _write_json_list
from models.schemas import ArtistCreate, ArtistTidalIdUpdate, ArtistsImportPayload
from services.releases_service import _artist_matches_route_id, _tidal_numeric_id_for_artist
from services.tidal_auth_service import load_tidal_session

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

    new_artist: dict = {"id": artist.id, "name": artist.name, "image_url": artist.image_url}
    if artist.spotify_id is not None:
        new_artist["spotify_id"] = str(artist.spotify_id).strip()
    if artist.tidal_id is not None and str(artist.tidal_id).strip():
        new_artist["tidal_id"] = str(artist.tidal_id).strip()
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


@router.patch("/artistas/{artist_id}")
def patch_artist(artist_id: str, body: ArtistTidalIdUpdate) -> dict:
    artists = _read_json_list(ARTISTS_FILE)
    found = False
    for item in artists:
        if _artist_matches_route_id(item, artist_id):
            found = True
            if body.tidal_id is None or not str(body.tidal_id).strip():
                item.pop("tidal_id", None)
            else:
                item["tidal_id"] = str(body.tidal_id).strip()
            break
    if not found:
        raise HTTPException(status_code=404, detail="Artist not found")
    artists.sort(key=lambda row: str(row.get("name", "")).lower())
    _write_json_list(ARTISTS_FILE, artists)
    return {"status": "ok"}


@router.delete("/artistas/{artist_id}")
def delete_artist(artist_id: str) -> dict[str, str]:
    artists = _read_json_list(ARTISTS_FILE)
    updated_artists = [item for item in artists if not _artist_matches_route_id(item, artist_id)]

    if len(updated_artists) == len(artists):
        raise HTTPException(status_code=404, detail="Artist not found")

    _write_json_list(ARTISTS_FILE, updated_artists)
    return {"status": "deleted"}


@router.post("/artistas/refresh")
def refresh_artists(only_missing_images: bool = False) -> dict:
    artists = _read_json_list(ARTISTS_FILE)
    if not artists:
        return {"status": "ok", "updated": 0, "total": 0}

    session = load_tidal_session()
    if session is None:
        return {"status": "ok", "updated": 0, "total": len(artists), "message": "Sessão Tidal em falta; nada atualizado."}

    updated = 0

    for artist in artists:
        tidal_key = _tidal_numeric_id_for_artist(artist)
        if not tidal_key:
            continue
        if only_missing_images and artist.get("image_url"):
            continue

        try:
            ta = session.artist(int(tidal_key))
        except Exception:
            continue

        changed = False
        tname = getattr(ta, "name", None)
        if tname and artist.get("name") != tname:
            artist["name"] = tname
            changed = True

        image_url = None
        try:
            if getattr(ta, "picture", None):
                image_url = ta.image(640)
        except Exception:
            image_url = None
        if image_url and artist.get("image_url") != image_url:
            artist["image_url"] = image_url
            changed = True

        if changed:
            updated += 1

    artists.sort(key=lambda item: str(item.get("name", "")).lower())
    _write_json_list(ARTISTS_FILE, artists)
    return {"status": "ok", "updated": updated, "total": len(artists)}
