"""Utilitários mínimos ligados ao ecossistema Spotify (ex.: cache OAuth do worker reverse)."""

from __future__ import annotations

import os
from pathlib import Path

from core.config import ROOT_DIR


def _reverse_spotify_cache_path() -> Path:
    raw = os.getenv("REVERSE_SPOTIFY_CACHE_PATH", "/data/spotify_oauth_cache_reverse.json").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / raw
    return path
