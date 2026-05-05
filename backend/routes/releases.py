from __future__ import annotations

from fastapi import APIRouter

from controllers import releases_controller as releases_ctrl
from models.schemas import (
    AlbumTrackItem,
    CsvReleaseAddPayload,
    PlaylistTrackLinksUpsertPayload,
    ReleaseItem,
    SpotifyArtistItem,
    TidalSpotiflacDownloadPayload,
)

router = APIRouter(tags=["releases"])


@router.get("/releases")
def list_releases(start_date: str | None = None, end_date: str | None = None) -> list[ReleaseItem]:
    return releases_ctrl.list_releases_catalog(start_date, end_date)


@router.get("/releases/local")
def list_local_releases() -> list[ReleaseItem]:
    return releases_ctrl.list_local_releases_from_disk()


@router.post("/releases/local/fetch")
def fetch_local_releases(
    period: str = "month", start_date: str | None = None, end_date: str | None = None
) -> dict:
    return releases_ctrl.start_fetch_local_job(period, start_date, end_date)


@router.get("/releases/local/fetch/{job_id}")
def get_local_fetch_job(job_id: str) -> dict:
    return releases_ctrl.get_local_fetch_job(job_id)


@router.get("/releases/tidal/session")
def tidal_session_status() -> dict:
    return releases_ctrl.tidal_session_status()


@router.post("/releases/tidal/device/start")
def tidal_device_start() -> dict:
    return releases_ctrl.tidal_device_start()


@router.get("/releases/tidal/device/status")
def tidal_device_status() -> dict:
    return releases_ctrl.tidal_device_status()


@router.get("/releases/tidal/albums/{album_id}/tracks")
def tidal_album_tracks(album_id: str) -> list[AlbumTrackItem]:
    return releases_ctrl.tidal_album_tracks(album_id)


@router.get("/releases/tidal/artists/search")
def search_tidal_artists(q: str, limit: int = 15) -> list[SpotifyArtistItem]:
    return releases_ctrl.search_tidal_artists(q, limit)


@router.get("/releases/tidal/tracks/search")
def search_tidal_tracks(q: str, limit: int = 15) -> list[AlbumTrackItem]:
    return releases_ctrl.search_tidal_tracks(q, limit)


@router.post("/releases/tidal/spotiflac-download")
def tidal_spotiflac_download(payload: TidalSpotiflacDownloadPayload) -> dict:
    return releases_ctrl.tidal_spotiflac_download(payload)


@router.get("/csv/releases")
def list_csv_releases() -> list[dict]:
    return releases_ctrl.list_csv_releases()


@router.post("/csv/releases")
def add_csv_release(payload: CsvReleaseAddPayload) -> dict:
    return releases_ctrl.add_csv_release(payload)


@router.delete("/csv/releases/{release_id}")
def delete_csv_release(release_id: str) -> dict[str, str]:
    return releases_ctrl.delete_csv_release(release_id)


@router.get("/releases/playlist-track-links")
def list_playlist_track_links() -> list[dict]:
    """Mapa videoId (YTM) → tidal_url / release_id — preenchido pelo worker ao adicionar à playlist de releases."""
    return releases_ctrl.list_playlist_track_links()


@router.post("/releases/playlist-track-links")
def upsert_playlist_track_links(payload: PlaylistTrackLinksUpsertPayload) -> dict[str, int | str]:
    return releases_ctrl.upsert_playlist_track_links(payload)


@router.post("/artistas/{artist_id}/releases/fetch")
def fetch_artist_releases_to_local(artist_id: str, period: str = "month", force: bool = False) -> dict:
    return releases_ctrl.fetch_artist_releases_to_local(artist_id, period, force)


@router.post("/releases/sync")
def start_releases_sync(start_date: str | None = None, end_date: str | None = None) -> dict[str, str]:
    return releases_ctrl.start_releases_sync(start_date, end_date)


@router.get("/releases/sync/{job_id}")
def get_releases_sync(job_id: str) -> dict:
    return releases_ctrl.get_releases_sync(job_id)
