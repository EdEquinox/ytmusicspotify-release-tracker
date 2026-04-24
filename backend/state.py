from __future__ import annotations

from threading import Lock

_release_jobs: dict[str, dict] = {}
_release_jobs_lock = Lock()
_local_fetch_jobs: dict[str, dict] = {}
_local_fetch_jobs_lock = Lock()
_settings_lock = Lock()
_spotify_token: str | None = None
_spotify_token_expires_at: float = 0.0
_spotify_backoff_until: float = 0.0
