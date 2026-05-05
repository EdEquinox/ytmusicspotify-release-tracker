from __future__ import annotations

from typing import Any

from services.backend_client import _search_tidal_tracks, _upsert_playlist_track_link
from services.tidal_search import _pick_tidal_track_url


def resolve_tidal_url_with_fallback(
    backend_url: str,
    video_id: str,
    artist: str,
    title: str,
    links_by_video: dict[str, dict[str, Any]],
    *,
    persist_if_searched: bool,
) -> str:
    """
    1) URL em playlist_track_links.json (videoId do like).
    2) Senão, pesquisa Tidal no backend (como Spotify.search + pick).
    3) Opcionalmente grava no JSON para likes antigos sem mapeamento.
    """
    vid = str(video_id or "").strip()
    link = links_by_video.get(vid) if vid else None
    cached = (str(link.get("tidal_url") or "").strip() if link else "") or ""
    if cached:
        return cached

    query = f"{artist} {title}".strip()
    if len(query) < 2:
        return ""
    rows = _search_tidal_tracks(backend_url, query, limit=10)
    picked = _pick_tidal_track_url(rows, artist, title) or ""
    if not picked.strip():
        return ""

    if persist_if_searched and vid:
        rid: str | None = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("tidal_url") or "").strip() == picked.strip():
                tid = str(row.get("id") or "").strip()
                rid = tid or None
                break
        _upsert_playlist_track_link(
            backend_url,
            yt_video_id=vid,
            tidal_url=picked.strip(),
            artist_name=artist,
            track_title=title,
            release_id=rid,
        )

    return picked.strip()
