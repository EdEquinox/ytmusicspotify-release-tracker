from __future__ import annotations

from pydantic import BaseModel, Field


class ArtistCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    image_url: str | None = None
    tidal_id: str | None = None
    spotify_id: str | None = None


class ArtistTidalIdUpdate(BaseModel):
    tidal_id: str | None = None


class SyncErrorCreate(BaseModel):
    track_name: str = Field(min_length=1)
    artist_name: str = Field(min_length=1)
    album_name: str | None = None
    reason: str = Field(min_length=1)
    spotify_url_manual: str | None = None
    tidal_url_manual: str | None = None
    release_id: str | None = None
    clear_csv_on_resolve: bool = False


class SyncErrorItem(SyncErrorCreate):
    id: str
    created_at: str
    attempts: int = Field(default=1, ge=1)


class SyncErrorLinksUpdate(BaseModel):
    spotify_url_manual: str | None = None
    tidal_url_manual: str | None = None


class SpotifyArtistItem(BaseModel):
    id: str
    name: str
    image_url: str | None = None


class ReleaseItem(BaseModel):
    id: str
    name: str
    artist_name: str
    release_date: str
    album_type: str
    spotify_url: str | None = None
    tidal_url: str | None = None
    source: str = "tidal"
    tracked_artist_id: str | None = None
    image_url: str | None = None
    matched_artists: list[str] = []
    has_non_primary_match: bool = False
    fetched_at: str | None = None


class AlbumTrackItem(BaseModel):
    id: str
    name: str
    artist_name: str
    spotify_url: str | None = None
    tidal_url: str | None = None
    duration_ms: int | None = None


class ReleaseSyncJob(BaseModel):
    id: str
    status: str
    progress: int
    processed_artists: int
    total_artists: int
    start_date: str
    end_date: str
    created_at: str
    updated_at: str
    releases: list[ReleaseItem] = []
    error: str | None = None


class CsvReleaseAddPayload(BaseModel):
    release_id: str | None = None
    id: str | None = None
    name: str | None = None
    artist_name: str | None = None
    album_type: str = "single"
    spotify_url: str | None = None
    tidal_url: str | None = None


class PlaylistTrackLinkItem(BaseModel):
    """Liga um videoId do YouTube Music (playlist de releases) a metadados Tidal para o reverse worker."""

    yt_video_id: str = Field(min_length=1)
    tidal_url: str | None = None
    release_id: str | None = None
    artist_name: str = ""
    release_name: str = ""


class PlaylistTrackLinksUpsertPayload(BaseModel):
    items: list[PlaylistTrackLinkItem]


class LocalFetchJob(BaseModel):
    id: str
    status: str
    period: str
    progress: int
    processed_artists: int
    total_artists: int
    fetched_releases: int
    stored_releases: int
    start_date: str | None = None
    end_date: str | None = None
    created_at: str
    updated_at: str
    error: str | None = None


class AppSettings(BaseModel):
    playlist_id: str = ""
    ytmusic_user: str = ""
    local_fetch_spacing_ms: int = 120
    release_workers: int = 10
    worker_idle_seconds: int = 20
    worker_processed_sleep_seconds: int = 10
    worker_backend_retry_seconds: int = 15
    worker_album_audio_only_strict: bool = True
    last_releases_fetch_end_date: str | None = None


class AppSettingsUpdate(BaseModel):
    playlist_id: str = ""
    ytmusic_user: str = ""
    local_fetch_spacing_ms: int = Field(default=120, ge=0, le=5000)
    release_workers: int = Field(default=10, ge=1, le=30)
    worker_idle_seconds: int = Field(default=20, ge=5, le=3600)
    worker_processed_sleep_seconds: int = Field(default=10, ge=1, le=600)
    worker_backend_retry_seconds: int = Field(default=15, ge=5, le=600)
    worker_album_audio_only_strict: bool = True


class ArtistsImportPayload(BaseModel):
    artists: list[ArtistCreate]
    replace: bool = False


class YTMusicAuthImportPayload(BaseModel):
    auth_json: dict


class HistoricoItem(BaseModel):
    id: str = Field(min_length=1)
    artista: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    created_at: str | None = None
