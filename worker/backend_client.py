from __future__ import annotations

from typing import Any

import requests


def _create_error(
    backend_url: str,
    release: dict[str, Any],
    reason: str,
    *,
    clear_csv_on_resolve: bool = False,
) -> None:
    release_id = str(release.get("id", "")).strip()
    payload: dict[str, Any] = {
        "track_name": str(release.get("name", "Unknown track")),
        "artist_name": str(release.get("artist_name", "Unknown artist")),
        "album_name": str(release.get("name", "Unknown release")),
        "reason": reason,
        "clear_csv_on_resolve": clear_csv_on_resolve,
    }
    if release_id:
        payload["release_id"] = release_id
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


def _fetch_backend_settings(backend_url: str) -> dict[str, Any]:
    response = requests.get(f"{backend_url}/settings", timeout=20)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    return {}
