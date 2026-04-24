from __future__ import annotations

from typing import Any

from matching import _is_close_title_match, _normalize_text


def _pick_video_id(search_results: list[dict[str, Any]], artist_name: str) -> str | None:
    normalized_artist = artist_name.lower().strip()
    for item in search_results:
        if str(item.get("videoType", "")).upper() == "MUSIC_VIDEO":
            continue
        artists = item.get("artists") or []
        artist_names = [str(artist.get("name", "")).lower() for artist in artists]
        if normalized_artist and any(normalized_artist in name for name in artist_names):
            return item.get("videoId")

    if search_results:
        for item in search_results:
            if str(item.get("videoType", "")).upper() != "MUSIC_VIDEO":
                return item.get("videoId")
    return None


def _pick_single_video_id(
    search_results: list[dict[str, Any]], artist_name: str, release_name: str
) -> str | None:
    normalized_artist = _normalize_text(artist_name)
    for item in search_results:
        if str(item.get("videoType", "")).upper() == "MUSIC_VIDEO":
            continue
        result_title = str(item.get("title", ""))
        if not _is_close_title_match(release_name, result_title):
            continue
        artists = item.get("artists") or []
        artist_names = [_normalize_text(str(artist.get("name", ""))) for artist in artists]
        if normalized_artist and any(normalized_artist in name for name in artist_names):
            return item.get("videoId")

    return None


def _pick_album_browse_id(search_results: list[dict[str, Any]], artist_name: str) -> str | None:
    normalized_artist = artist_name.lower().strip()
    for item in search_results:
        artists = item.get("artists") or []
        artist_names = [str(artist.get("name", "")).lower() for artist in artists]
        if normalized_artist and any(normalized_artist in name for name in artist_names):
            return item.get("browseId")

    if search_results:
        return search_results[0].get("browseId")
    return None
