from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
ARTISTS_FILE = DATA_DIR / "artists.json"
ERRORS_FILE = DATA_DIR / "errors.json"
RELEASES_FILE = DATA_DIR / "releases.json"
RELEASE_FETCH_STATE_FILE = DATA_DIR / "release_fetch_state.json"
TIDAL_SESSION_FILE = Path(os.getenv("TIDAL_SESSION_FILE", str(DATA_DIR / "tidal_session.json"))).resolve()
CSV_RELEASES_FILE = DATA_DIR / "csv_releases.json"
PLAYLIST_TRACK_LINKS_FILE = DATA_DIR / "playlist_track_links.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORICO_FILE = DATA_DIR / "historico.json"
SPOTIFY_ACCOUNTS_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1"
DEFAULT_WORKERS = 10
