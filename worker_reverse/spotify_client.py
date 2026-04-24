from __future__ import annotations

from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from backend_client import _read_settings


def _build_spotify_client(
    backend_url: str,
    cache_path: str,
    default_client_id: str,
    default_client_secret: str,
    default_redirect_uri: str,
) -> tuple[spotipy.Spotify, SpotifyOAuth]:
    settings: dict[str, Any] = {}
    try:
        settings = _read_settings(backend_url)
    except Exception:
        # Backend may not be up yet; fallback to env values for startup resilience.
        settings = {}

    client_id = str(
        settings.get("spotify_oauth_client_id")
        or settings.get("spotify_client_id")
        or default_client_id
    ).strip()
    client_secret = str(settings.get("spotify_client_secret") or default_client_secret).strip()
    redirect_uri = str(
        settings.get("reverse_spotify_redirect_uri")
        or settings.get("spotify_oauth_redirect_uri")
        or default_redirect_uri
    ).strip()
    if not client_id or not client_secret:
        raise RuntimeError("Spotify OAuth credentials missing. Configure in Settings or env.")
    if not redirect_uri:
        raise RuntimeError("Spotify OAuth redirect URI missing. Configure in Settings or env.")
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-modify-private playlist-modify-public",
        cache_path=cache_path,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager), auth_manager


def _ensure_spotify_token_non_interactive(auth_manager: SpotifyOAuth) -> bool:
    token_info = auth_manager.cache_handler.get_cached_token()
    if token_info:
        return True
    auth_url = auth_manager.get_authorize_url()
    print("[reverse] Spotify OAuth token not found in cache.")
    print(f"[reverse] Authorize once via this URL, then paste redirected URL into spotipy setup flow: {auth_url}")
    print("[reverse] After token is cached, worker will continue automatically.")
    return False
