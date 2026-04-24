from __future__ import annotations

from typing import Any

import requests

from matching import _normalize, _track_key


def _read_settings(backend_url: str) -> dict[str, Any]:
    response = requests.get(f"{backend_url}/settings", timeout=20)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _list_historico_ids(backend_url: str) -> set[str]:
    response = requests.get(f"{backend_url}/historico", timeout=20)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        return set()
    return {str(item.get("id", "")).strip() for item in rows if str(item.get("id", "")).strip()}


def _add_historico(backend_url: str, track_id: str, artist: str, title: str) -> None:
    requests.post(
        f"{backend_url}/historico",
        timeout=20,
        json={"id": track_id, "artista": artist, "titulo": title},
    ).raise_for_status()


def _report_not_found(backend_url: str, artist: str, title: str) -> None:
    requests.post(
        f"{backend_url}/erros",
        timeout=20,
        json={
            "track_name": title,
            "artist_name": artist,
            "reason": f"NAO_NO_SPOTIFY: Aprovada no YTM, mas nao encontrada no Spotify ({artist} - {title})",
        },
    ).raise_for_status()


def _report_error(backend_url: str, artist: str, title: str, reason: str) -> None:
    requests.post(
        f"{backend_url}/erros",
        timeout=20,
        json={
            "track_name": title,
            "artist_name": artist,
            "reason": reason,
        },
    ).raise_for_status()


def _list_errors(backend_url: str) -> list[dict[str, Any]]:
    response = requests.get(f"{backend_url}/erros", timeout=20)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _extract_manual_spotify_links(errors: list[dict[str, Any]]) -> dict[str, str]:
    manual_links: dict[str, str] = {}
    for item in errors:
        artist = str(item.get("artist_name", "")).strip()
        title = str(item.get("track_name", "")).strip()
        link = str(item.get("spotify_url_manual", "")).strip()
        if not artist or not title or not link:
            continue
        manual_links[_track_key(artist, title)] = link
    return manual_links


def _clear_resolved_errors(backend_url: str, artist: str, title: str) -> None:
    try:
        response = requests.get(f"{backend_url}/erros", timeout=20)
        response.raise_for_status()
        rows = response.json()
    except Exception:
        return

    if not isinstance(rows, list):
        return

    artist_norm = _normalize(artist)
    title_norm = _normalize(title)
    for item in rows:
        current_artist = _normalize(str(item.get("artist_name", "")))
        current_title = _normalize(str(item.get("track_name", "")))
        reason = str(item.get("reason", ""))
        if current_artist != artist_norm or current_title != title_norm:
            continue
        if not (
            reason.startswith("DOWNLOAD_SPOTIFLAC:")
            or reason.startswith("NAO_NO_SPOTIFY:")
        ):
            continue
        error_id = str(item.get("id", "")).strip()
        if not error_id:
            continue
        try:
            requests.delete(f"{backend_url}/erros/{error_id}", timeout=20).raise_for_status()
        except Exception:
            continue
