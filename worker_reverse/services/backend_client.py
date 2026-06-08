from __future__ import annotations

from typing import Any

import requests

from services.matching import _normalize, _track_key


def _search_tidal_tracks(backend_url: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Pesquisa faixas no Tidal via backend (sessão tidal_session.json)."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    try:
        response = requests.get(
            f"{backend_url}/releases/tidal/tracks/search",
            params={"q": q, "limit": str(min(max(limit, 1), 25))},
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _upsert_playlist_track_link(
    backend_url: str,
    *,
    yt_video_id: str,
    tidal_url: str,
    artist_name: str,
    track_title: str,
    release_id: str | None = None,
) -> None:
    """Grava no JSON para o próximo ciclo não precisar de pesquisar outra vez."""
    if not str(yt_video_id).strip() or not str(tidal_url).strip():
        return
    payload = {
        "items": [
            {
                "yt_video_id": str(yt_video_id).strip(),
                "tidal_url": str(tidal_url).strip(),
                "release_id": (release_id or "").strip() or None,
                "artist_name": (artist_name or "").strip(),
                "release_name": (track_title or "").strip(),
            }
        ]
    }
    try:
        r = requests.post(
            f"{backend_url}/releases/playlist-track-links",
            json=payload,
            timeout=20,
        )
        if not r.ok:
            print(f"[reverse] playlist-track-links upsert HTTP {r.status_code}: {(r.text or '')[:120]}")
    except Exception as exc:
        print(f"[reverse] Falha a gravar playlist-track-links: {exc}")


def _fetch_playlist_track_links(backend_url: str) -> dict[str, dict[str, Any]]:
    """videoId YouTube Music → linha com tidal_url (preenchido pelo worker de releases)."""
    try:
        response = requests.get(f"{backend_url}/releases/playlist-track-links", timeout=20)
        response.raise_for_status()
        rows = response.json()
    except Exception:
        return {}
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        vid = str(row.get("yt_video_id", "")).strip()
        if vid:
            out[vid] = row if isinstance(row, dict) else {}
    return out


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
