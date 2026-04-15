from __future__ import annotations

import os
import time
from typing import Any

import requests
import json
from ytmusicapi import YTMusic
from ytmusicapi.helpers import get_authorization, sapisid_from_cookie


def _build_query(release: dict[str, Any]) -> str:
    name = str(release.get("name", "")).strip()
    artist_name = str(release.get("artist_name", "")).strip()
    return f"{name} {artist_name}".strip()


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().replace("-", " ").replace("_", " ").split())


def _is_close_title_match(left: str, right: str) -> bool:
    left_norm = _normalize_text(left)
    right_norm = _normalize_text(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    return left_norm in right_norm or right_norm in left_norm


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


def _album_track_video_ids(ytmusic: YTMusic, browse_id: str) -> list[str]:
    album = ytmusic.get_album(browse_id)
    tracks = album.get("tracks") or []
    video_ids: list[str] = []
    for track in tracks:
        video_id = track.get("videoId")
        if video_id:
            video_ids.append(video_id)
    return video_ids


def _album_audio_only_video_ids(
    ytmusic: YTMusic, browse_id: str, release_artist_name: str
) -> tuple[list[str], int]:
    album = ytmusic.get_album(browse_id)
    tracks = album.get("tracks") or []
    audio_video_ids: list[str] = []
    fallback_failures = 0

    for track in tracks:
        track_video_id = track.get("videoId")
        track_title = str(track.get("title", "")).strip()
        track_artists = track.get("artists") or []
        primary_track_artist = (
            str(track_artists[0].get("name", "")).strip()
            if track_artists
            else release_artist_name
        )

        # When album track points to a music video, force a song-only fallback.
        if track_video_id:
            try:
                track_details = ytmusic.get_song(track_video_id) or {}
                video_details = track_details.get("videoDetails") or {}
                if str(video_details.get("musicVideoType", "")).upper() == "MUSIC_VIDEO":
                    track_video_id = None
            except Exception:
                # If metadata lookup fails, fallback to strict search path.
                track_video_id = None

        if track_video_id:
            audio_video_ids.append(track_video_id)
            continue

        if not track_title:
            fallback_failures += 1
            continue

        fallback_query = f"{track_title} {primary_track_artist}".strip()
        try:
            search_results = ytmusic.search(fallback_query, filter="songs", limit=5)
            fallback_video_id = _pick_single_video_id(
                search_results, primary_track_artist, track_title
            )
        except Exception:
            fallback_video_id = None

        if fallback_video_id:
            audio_video_ids.append(fallback_video_id)
        else:
            fallback_failures += 1

    return audio_video_ids, fallback_failures


def _create_error(backend_url: str, release: dict[str, Any], reason: str) -> None:
    payload = {
        "track_name": str(release.get("name", "Unknown track")),
        "artist_name": str(release.get("artist_name", "Unknown artist")),
        "album_name": str(release.get("name", "Unknown release")),
        "reason": reason,
    }
    try:
        requests.post(f"{backend_url}/erros", json=payload, timeout=20)
    except Exception as exc:
        print(f"[worker] Failed to persist sync error: {exc}")


def _delete_csv_item(backend_url: str, release_id: str) -> None:
    try:
        requests.delete(f"{backend_url}/csv/releases/{release_id}", timeout=20)
    except Exception as exc:
        print(f"[worker] Failed to remove release from CSV list: {release_id} ({exc})")


def _fetch_csv_releases(backend_url: str) -> list[dict[str, Any]]:
    response = requests.get(f"{backend_url}/csv/releases", timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    return payload


def _playlist_track_count(ytmusic: YTMusic, playlist_id: str) -> int:
    playlist = ytmusic.get_playlist(playlist_id, limit=1)
    raw_count = playlist.get("trackCount")
    try:
        return int(raw_count)
    except Exception:
        tracks = playlist.get("tracks") or []
        return len(tracks)


def _has_duplicates_confirm_dialog(add_result: dict[str, Any]) -> bool:
    if str(add_result.get("status")) != "STATUS_FAILED":
        return False
    actions = add_result.get("actions") or []
    if not actions:
        return False
    first_action = actions[0] or {}
    endpoint = first_action.get("confirmDialogEndpoint") or {}
    content = endpoint.get("content") or {}
    renderer = content.get("confirmDialogRenderer") or {}
    title_runs = (renderer.get("title") or {}).get("runs") or []
    title = " ".join(str(item.get("text", "")) for item in title_runs).lower()
    return "duplicate" in title


def _add_result_indicates_success(add_result: dict[str, Any]) -> bool:
    status = str(add_result.get("status", "")).upper()
    return status in {"STATUS_SUCCEEDED", "STATUS_SUCCESS"}


def _fetch_backend_settings(backend_url: str) -> dict[str, Any]:
    response = requests.get(f"{backend_url}/settings", timeout=20)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    return {}


def _is_ytmusic_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "401" in message
        or "unauthorized" in message
        or "authentication credential" in message
        or "login required" in message
    )


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
                _delete_csv_item(backend_url, release_id)
                print(f"[worker] Added to playlist ({count_after - count_before} new track(s)): {query}")
            elif _add_result_indicates_success(add_result):
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


def _load_ytmusic_client(auth_file: str, user_id: str | None = None) -> YTMusic:
    with open(auth_file, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid YTMUSIC auth file format")

    # Support browser-header JSON auth format (cookie/origin keys).
    if "cookie" in payload:
        cookie = str(payload.get("cookie", ""))
        origin = str(payload.get("origin", "https://music.youtube.com"))
        if not cookie:
            raise RuntimeError("ytmusic_auth.json missing cookie")

        sapisid = sapisid_from_cookie(cookie)
        authorization = get_authorization(f"{sapisid} {origin}")
        headers = {
            "cookie": cookie,
            "origin": origin,
            "user-agent": str(payload.get("user-agent", "")),
            "x-goog-authuser": str(payload.get("x-goog-authuser", "0")),
            "x-goog-visitor-id": str(payload.get("x-goog-visitor-id", "")),
            "authorization": authorization,
        }
        return YTMusic(auth=headers, user=user_id or None)

    # Novo: Lê o client_id e client_secret diretamente de dentro do ytmusic_auth.json
    client_id = payload.get("client_id")
    client_secret = payload.get("client_secret")

    if client_id and client_secret:
        return YTMusic(
            auth=auth_file, 
            user=user_id or None,
            oauth_credentials={
                "client_id": str(client_id).strip(),
                "client_secret": str(client_secret).strip()
            }
        )

    # Fallback caso não encontre as chaves no ficheiro
    return YTMusic(auth=auth_file, user=user_id or None)


def main() -> None:
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")
    interval = int(os.getenv("WORKER_INTERVAL_SECONDS", "300"))
    backend_retry_seconds = 15
    idle_seconds = 20
    processed_seconds = 10
    playlist_id = ""
    auth_file = os.getenv("YTMUSIC_AUTH_FILE", "/data/ytmusic_auth.json").strip()
    ytmusic_user = os.getenv("YTMUSIC_USER", "").strip()

    print(
        f"Worker started. Backend: {backend_url}. Interval: {interval}s. "
        f"Auth file: {auth_file}. Playlist: {playlist_id}. User: {ytmusic_user or 'default'}"
    )
    ytmusic = _load_ytmusic_client(auth_file, ytmusic_user or None)

    while True:
        strict_audio_only = True
        try:
            settings = _fetch_backend_settings(backend_url)
            playlist_id = str(settings.get("playlist_id", "")).strip() or playlist_id
            backend_retry_seconds = int(settings.get("worker_backend_retry_seconds", backend_retry_seconds))
            idle_seconds = int(settings.get("worker_idle_seconds", idle_seconds))
            processed_seconds = int(
                settings.get("worker_processed_sleep_seconds", processed_seconds)
            )
            strict_audio_only = bool(
                settings.get("worker_album_audio_only_strict", strict_audio_only)
            )
        except Exception as exc:
            print(f"[worker] Failed to load backend settings, using current playlist id: {exc}")

        if not playlist_id:
            print("[worker] Missing playlist id in env/backend settings. Retrying later.")
            time.sleep(backend_retry_seconds)
            continue

        cycle_result = _sync_cycle(backend_url, ytmusic, playlist_id, strict_audio_only)
        if cycle_result == "backend_error":
            print(f"[worker] Sleeping {backend_retry_seconds}s (backend retry)")
            time.sleep(backend_retry_seconds)
        elif cycle_result == "ytmusic_auth_error":
            print("[worker] Attempting to reload YTMusic auth from file...")
            try:
                ytmusic = _load_ytmusic_client(auth_file, ytmusic_user or None)
                print("[worker] YTMusic auth reloaded. If 401 persists, reimport auth JSON in frontend.")
            except Exception as exc:
                print(f"[worker] Failed to reload YTMusic auth file: {exc}")
            time.sleep(backend_retry_seconds)
        elif cycle_result == "idle":
            print(f"[worker] Sleeping {idle_seconds}s (queue idle)")
            time.sleep(idle_seconds)
        else:
            # After successful processing, recheck quickly for newly queued releases.
            print(f"[worker] Sleeping {processed_seconds}s (post-processing)")
            time.sleep(processed_seconds)


if __name__ == "__main__":
    main()
