from __future__ import annotations

import os
import time

from ytmusicapi import YTMusic

from backend_client import _read_settings
from spotiflac_download import _normalize_spotiflac_template
from spotify_client import _build_spotify_client, _ensure_spotify_token_non_interactive
from sync_likes import _sync_likes_cycle
from ytmusic_auth import _is_ytmusic_auth_error


def _load_ytmusic_client(auth_file: str) -> YTMusic:
    print("[DEBUG] Inicializando YTMusic com Cookies (Browser Session)...")
    return YTMusic(auth=auth_file)


def main() -> None:
    backend_url = os.getenv("REVERSE_BACKEND_URL", "http://backend:8000").rstrip("/")
    ytmusic_auth_file = os.getenv("REVERSE_YTMUSIC_AUTH_FILE", "/data/ytmusic_auth.json").strip()
    spotify_playlist_id = ""
    spotify_client_id = ""
    spotify_client_secret = ""
    spotify_redirect_uri = ""
    spotify_cache_path = os.getenv("REVERSE_SPOTIFY_CACHE_PATH", "/data/spotify_oauth_cache_reverse.json").strip()
    poll_seconds = 300
    liked_limit = 100
    reverse_redirect_uri = spotify_redirect_uri
    add_to_playlist = True
    spotiflac_enabled = False
    spotiflac_output_dir = "/data/downloads"
    spotiflac_command_template = 'spotiflac "{spotify_url}" "{output_dir}"'
    spotiflac_command_template = _normalize_spotiflac_template(spotiflac_command_template)
    spotiflac_timeout_seconds = 600
    spotiflac_loop_minutes = 0
    reverse_track_spacing_ms = 0
    # Force strict service selection: only Tidal.
    spotiflac_services = ["tidal"]
    spotiflac_filename_format = os.getenv(
        "REVERSE_SPOTIFLAC_FILENAME_FORMAT",
        "{title} - {artist}",
    ).strip() or "{title} - {artist}"
    spotiflac_use_artist_subfolders = (
        os.getenv("REVERSE_SPOTIFLAC_USE_ARTIST_SUBFOLDERS", "true").strip().lower() != "false"
    )
    spotiflac_use_album_subfolders = (
        os.getenv("REVERSE_SPOTIFLAC_USE_ALBUM_SUBFOLDERS", "true").strip().lower() != "false"
    )

    print(
        f"[reverse] Worker started. Backend={backend_url} Playlist={spotify_playlist_id} "
        f"LikedLimit={liked_limit} Poll={poll_seconds}s"
    )

    ytmusic = _load_ytmusic_client(ytmusic_auth_file)
    spotify, spotify_auth_manager = _build_spotify_client(
        backend_url,
        spotify_cache_path,
        spotify_client_id,
        spotify_client_secret,
        reverse_redirect_uri,
    )

    while True:
        try:
            settings = _read_settings(backend_url)
            spotify_playlist_id = (
                str(settings.get("reverse_spotify_playlist_id") or spotify_playlist_id).strip()
            )
            liked_limit = max(int(settings.get("reverse_liked_limit", liked_limit)), 1)
            poll_seconds = max(int(settings.get("reverse_poll_seconds", poll_seconds)), 30)
            add_to_playlist = bool(settings.get("reverse_spotify_add_to_playlist", add_to_playlist))
            spotiflac_enabled = bool(settings.get("reverse_spotiflac_enabled", spotiflac_enabled))
            spotiflac_output_dir = str(settings.get("reverse_spotiflac_output_dir", spotiflac_output_dir)).strip() or "/data/downloads"
            spotiflac_command_template = (
                str(settings.get("reverse_spotiflac_command_template", spotiflac_command_template)).strip()
                or 'spotiflac "{spotify_url}" "{output_dir}"'
            )
            spotiflac_command_template = _normalize_spotiflac_template(spotiflac_command_template)
            spotiflac_timeout_seconds = max(
                int(settings.get("reverse_spotiflac_timeout_seconds", spotiflac_timeout_seconds)),
                10,
            )
            spotiflac_loop_minutes = max(
                int(settings.get("reverse_spotiflac_loop_minutes", spotiflac_loop_minutes)),
                0,
            )
            reverse_track_spacing_ms = max(
                int(settings.get("reverse_track_spacing_ms", reverse_track_spacing_ms)),
                0,
            )
            # Keep strict service selection independent from settings/env.
            spotiflac_services = ["tidal"]
            spotiflac_filename_format = (
                str(settings.get("reverse_spotiflac_filename_format", spotiflac_filename_format)).strip()
                or spotiflac_filename_format
            )
            spotiflac_use_artist_subfolders = bool(
                settings.get("reverse_spotiflac_use_artist_subfolders", spotiflac_use_artist_subfolders)
            )
            spotiflac_use_album_subfolders = bool(
                settings.get("reverse_spotiflac_use_album_subfolders", spotiflac_use_album_subfolders)
            )
            configured_redirect = str(settings.get("reverse_spotify_redirect_uri", "")).strip()
            if configured_redirect and configured_redirect != reverse_redirect_uri:
                reverse_redirect_uri = configured_redirect
                spotify, spotify_auth_manager = _build_spotify_client(
                    backend_url,
                    spotify_cache_path,
                    spotify_client_id,
                    spotify_client_secret,
                    reverse_redirect_uri,
                )
            if add_to_playlist and not spotify_playlist_id:
                raise RuntimeError("Missing reverse_spotify_playlist_id in Settings (or REVERSE_SPOTIFY_PLAYLIST_ID env).")
            if not _ensure_spotify_token_non_interactive(spotify_auth_manager):
                time.sleep(poll_seconds)
                continue
            _sync_likes_cycle(
                backend_url=backend_url,
                ytmusic=ytmusic,
                spotify=spotify,
                spotify_playlist_id=spotify_playlist_id,
                liked_limit=liked_limit,
                add_to_playlist=add_to_playlist,
                spotiflac_enabled=spotiflac_enabled,
                spotiflac_output_dir=spotiflac_output_dir,
                spotiflac_command_template=spotiflac_command_template,
                spotiflac_timeout_seconds=spotiflac_timeout_seconds,
                spotiflac_services=spotiflac_services,
                spotiflac_filename_format=spotiflac_filename_format,
                spotiflac_use_artist_subfolders=spotiflac_use_artist_subfolders,
                spotiflac_use_album_subfolders=spotiflac_use_album_subfolders,
                reverse_track_spacing_ms=reverse_track_spacing_ms,
                spotiflac_loop_minutes=spotiflac_loop_minutes,
            )
        except Exception as exc:
            print(f"[reverse] Sync cycle failed: {exc}")
            if _is_ytmusic_auth_error(exc):
                print("[reverse] Attempting to reload YTMusic auth from file...")
                try:
                    ytmusic = _load_ytmusic_client(ytmusic_auth_file)
                    print(
                        "[reverse] YTMusic auth reloaded. If 401 persists, reimport auth JSON in frontend."
                    )
                except Exception as reload_exc:
                    print(f"[reverse] Failed to reload YTMusic auth file: {reload_exc}")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
