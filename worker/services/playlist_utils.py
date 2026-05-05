from __future__ import annotations

from typing import Any

from ytmusicapi import YTMusic


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


def _is_ytmusic_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "401" in message
        or "unauthorized" in message
        or "authentication credential" in message
        or "login required" in message
    )
