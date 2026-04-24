from __future__ import annotations

from typing import Any

from matching import _normalize


def _extract_spotify_track_id_from_url(url: str) -> str | None:
    value = url.strip()
    if not value:
        return None
    if "open.spotify.com/track/" in value:
        tail = value.split("open.spotify.com/track/", 1)[1]
        track_id = tail.split("?", 1)[0].split("/", 1)[0].strip()
        return track_id or None
    if value.startswith("spotify:track:"):
        track_id = value.split("spotify:track:", 1)[1].strip()
        return track_id or None
    return None


def _pick_spotify_track_id(results: dict[str, Any], artist: str, title: str) -> str | None:
    tracks = (((results or {}).get("tracks") or {}).get("items") or [])
    target_artist = _normalize(artist)
    target_title = _normalize(title)
    for item in tracks:
        result_title = _normalize(str(item.get("name", "")))
        if target_title and target_title not in result_title and result_title not in target_title:
            continue
        artists = item.get("artists") or []
        artist_names = [_normalize(str(row.get("name", ""))) for row in artists]
        if target_artist and any(target_artist in current for current in artist_names):
            return str(item.get("id", "")).strip() or None
    if tracks:
        return str(tracks[0].get("id", "")).strip() or None
    return None
