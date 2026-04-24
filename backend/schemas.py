from __future__ import annotations

from pydantic import BaseModel, Field


class ArtistCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    image_url: str | None = None


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
    auto_fetch_enabled: bool = False
    auto_fetch_time: str = "04:00"
    auto_fetch_window_days: int = 1
    spotify_include_groups: str = "album,single"
    spotify_market: str = ""
    local_fetch_spacing_ms: int = 120
    release_workers: int = 10
    worker_idle_seconds: int = 20
    worker_processed_sleep_seconds: int = 10
    worker_backend_retry_seconds: int = 15
    worker_album_audio_only_strict: bool = True
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_oauth_client_id: str = ""
    spotify_oauth_redirect_uri: str = ""
    reverse_spotify_playlist_id: str = ""
    reverse_poll_seconds: int = 300
    reverse_liked_limit: int = 100
    reverse_spotify_redirect_uri: str = "http://localhost:8080/callback"
    reverse_spotify_add_to_playlist: bool = True
    reverse_spotiflac_enabled: bool = False
    reverse_spotiflac_output_dir: str = "/data/downloads"
    reverse_spotiflac_command_template: str = (
        'spotiflac "{spotify_url}" "{output_dir}"'
    )
    reverse_spotiflac_timeout_seconds: int = 600
    reverse_spotiflac_loop_minutes: int = 0
    reverse_track_spacing_ms: int = 0
    last_auto_fetch_date: str | None = None


class AppSettingsUpdate(BaseModel):
    playlist_id: str = ""
    auto_fetch_enabled: bool = False
    auto_fetch_time: str = "04:00"
    auto_fetch_window_days: int = Field(default=1, ge=1, le=30)
    spotify_include_groups: str = "album,single"
    spotify_market: str = ""
    local_fetch_spacing_ms: int = Field(default=120, ge=0, le=5000)
    release_workers: int = Field(default=10, ge=1, le=30)
    worker_idle_seconds: int = Field(default=20, ge=5, le=3600)
    worker_processed_sleep_seconds: int = Field(default=10, ge=1, le=600)
    worker_backend_retry_seconds: int = Field(default=15, ge=5, le=600)
    worker_album_audio_only_strict: bool = True
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_oauth_client_id: str = ""
    spotify_oauth_redirect_uri: str = ""
    reverse_spotify_playlist_id: str = ""
    reverse_poll_seconds: int = Field(default=300, ge=30, le=86400)
    reverse_liked_limit: int = Field(default=100, ge=1, le=5000)
    reverse_spotify_redirect_uri: str = "http://localhost:8080/callback"
    reverse_spotify_add_to_playlist: bool = True
    reverse_spotiflac_enabled: bool = False
    reverse_spotiflac_output_dir: str = "/data/downloads"
    reverse_spotiflac_command_template: str = (
        'spotiflac "{spotify_url}" "{output_dir}"'
    )
    reverse_spotiflac_timeout_seconds: int = Field(default=600, ge=10, le=86400)
    reverse_spotiflac_loop_minutes: int = Field(default=0, ge=0, le=1440)
    reverse_track_spacing_ms: int = Field(default=0, ge=0, le=30000)


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


class ReverseSpotifyOAuthCompletePayload(BaseModel):
    response_url: str = Field(min_length=1)


class SpotifySpotiflacDownloadPayload(BaseModel):
    spotify_url: str = Field(min_length=1)
