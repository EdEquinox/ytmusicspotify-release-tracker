from __future__ import annotations

import time
from typing import Any

from ytmusicapi import YTMusic

from services.album_tracks import _album_audio_only_video_ids, _album_track_video_ids
from services.backend_client import (
    _create_error,
    _delete_csv_item,
    _fetch_csv_releases,
    _upsert_playlist_track_links,
)
from services.matching import _build_query
from services.playlist_utils import (
    _add_result_indicates_success,
    _has_duplicates_confirm_dialog,
    _is_ytmusic_auth_error,
    _playlist_track_count,
)
from services.search_pickers import _pick_album_browse_id, _pick_single_video_id, _pick_video_id


def _sync_cycle(
    backend_url: str, ytmusic: YTMusic, playlist_id: str, strict_audio_only: bool = True
) -> str:
    had_processed_items = False
    try:
        releases = _fetch_csv_releases(backend_url)
    except Exception as exc:
        print(f"[worker] Failed to load CSV releases: {exc}")
        return "backend_error"

    if not releases:
        print("[worker] Queue check: no releases pending in csv_releases.json")
        return "idle"

    print(f"[worker] Processing {len(releases)} releases from CSV queue")
    for release in releases:
        had_processed_items = True
        release_id = str(release.get("id", "")).strip()
        query = _build_query(release)
        album_type = str(release.get("album_type", "")).lower().strip()
        if not release_id or not query:
            _create_error(backend_url, release, "Invalid release payload (missing id/name)")
            continue

        try:
            if album_type in {"album", "compilation"}:
                search_results = ytmusic.search(query, filter="albums", limit=5)
                browse_id = _pick_album_browse_id(search_results, str(release.get("artist_name", "")))
                if not browse_id:
                    _create_error(backend_url, release, f"Album not found on YTMusic for query: {query}")
                    continue
                if strict_audio_only:
                    video_ids, fallback_failures = _album_audio_only_video_ids(
                        ytmusic, browse_id, str(release.get("artist_name", ""))
                    )
                    if fallback_failures > 0:
                        _create_error(
                            backend_url,
                            release,
                            f"Album strict mode: {fallback_failures} track(s) could not be mapped to audio-only results.",
                        )
                else:
                    video_ids = _album_track_video_ids(ytmusic, browse_id)
                if not video_ids:
                    _create_error(
                        backend_url, release, f"Album found but without playable tracks on YTMusic: {query}"
                    )
                    continue
            elif album_type == "single":
                search_results = ytmusic.search(query, filter="songs", limit=5)
                video_id = _pick_single_video_id(
                    search_results, str(release.get("artist_name", "")), str(release.get("name", ""))
                )
                if not video_id:
                    _create_error(
                        backend_url,
                        release,
                        f"Single match not strict enough on YTMusic for query: {query}",
                    )
                    continue
                video_ids = [video_id]
            else:
                search_results = ytmusic.search(query, filter="songs", limit=5)
                video_id = _pick_video_id(search_results, str(release.get("artist_name", "")))
                if not video_id:
                    _create_error(backend_url, release, f"Track not found on YTMusic for query: {query}")
                    continue
                video_ids = [video_id]
        except Exception as exc:
            if _is_ytmusic_auth_error(exc):
                print(f"[worker] YTMusic auth error during search: {exc}")
                return "ytmusic_auth_error"
            _create_error(backend_url, release, f"Failed to search on YTMusic: {exc}")
            print(f"[worker] Search failed for '{query}': {exc}")
            continue
        try:
            count_before = _playlist_track_count(ytmusic, playlist_id)
            add_result = ytmusic.add_playlist_items(playlist_id, video_ids, duplicates=False)
            if _has_duplicates_confirm_dialog(add_result):
                print("[worker] Duplicate confirmation detected, retrying with duplicates=True")
                add_result = ytmusic.add_playlist_items(playlist_id, video_ids, duplicates=True)
            count_after = _playlist_track_count(ytmusic, playlist_id)
            if count_after == count_before:
                # Playlist counters may lag briefly; verify once more.
                time.sleep(2)
                count_after = _playlist_track_count(ytmusic, playlist_id)
            print(
                f"[worker] add_playlist_items result: {add_result}; "
                f"count_before={count_before}; count_after={count_after}"
            )
            if count_after > count_before:
                _upsert_playlist_track_links(backend_url, video_ids, release)
                _delete_csv_item(backend_url, release_id)
                print(f"[worker] Added to playlist ({count_after - count_before} new track(s)): {query}")
            elif _add_result_indicates_success(add_result):
                _upsert_playlist_track_links(backend_url, video_ids, release)
                _delete_csv_item(backend_url, release_id)
                print(
                    "[worker] Add reported success but playlist count did not change immediately; "
                    f"assuming success for: {query}"
                )
            else:
                _create_error(
                    backend_url,
                    release,
                    "No visible playlist change after add operation (possibly duplicates/wrong playlist context).",
                )
                print(f"[worker] No playlist change detected for: {query}")
        except Exception as exc:
            if _is_ytmusic_auth_error(exc):
                print(f"[worker] YTMusic auth error during add to playlist: {exc}")
                return "ytmusic_auth_error"
            _create_error(backend_url, release, f"Failed to add on YTMusic: {exc}")
            print(f"[worker] Add-to-playlist failed for '{query}': {exc}")
    return "processed" if had_processed_items else "idle"
