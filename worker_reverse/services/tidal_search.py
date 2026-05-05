from __future__ import annotations

from typing import Any

from services.matching import _normalize


def _pick_tidal_track_url(rows: list[dict[str, Any]], artist: str, title: str) -> str | None:
    """Escolhe URL Tidal a partir dos resultados da API (mesma ideia que _pick_spotify_track_id)."""
    target_artist = _normalize(artist)
    target_title = _normalize(title)
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("tidal_url") or "").strip()
        if not url:
            continue
        result_title = _normalize(str(row.get("name", "")))
        if target_title and target_title not in result_title and result_title not in target_title:
            continue
        result_artist = _normalize(str(row.get("artist_name", "")))
        if target_artist and target_artist not in result_artist and result_artist not in target_artist:
            continue
        return url
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("tidal_url") or "").strip()
        if url:
            return url
    return None
