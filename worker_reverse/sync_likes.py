from __future__ import annotations

import time

import spotipy
from ytmusicapi import YTMusic

from backend_client import (
    _add_historico,
    _clear_resolved_errors,
    _extract_manual_spotify_links,
    _list_errors,
    _list_historico_ids,
    _report_error,
    _report_not_found,
)
from matching import _track_key
from spotiflac_download import _download_with_spotiflac
from spotify_search import _extract_spotify_track_id_from_url, _pick_spotify_track_id


def _sync_likes_cycle(
    backend_url: str,
    ytmusic: YTMusic,
    spotify: spotipy.Spotify,
    spotify_playlist_id: str,
    liked_limit: int,
    add_to_playlist: bool,
    spotiflac_enabled: bool,
    spotiflac_output_dir: str,
    spotiflac_command_template: str,
    spotiflac_timeout_seconds: int,
    spotiflac_services: list[str],
    spotiflac_filename_format: str,
    spotiflac_use_artist_subfolders: bool,
    spotiflac_use_album_subfolders: bool,
    reverse_track_spacing_ms: int,
    spotiflac_loop_minutes: int,
) -> None:
    historico_ids = _list_historico_ids(backend_url)
    manual_spotify_links: dict[str, str] = {}
    try:
        manual_spotify_links = _extract_manual_spotify_links(_list_errors(backend_url))
    except Exception as exc:
        print(f"[reverse] Failed to load manual Spotify links from errors: {exc}")
    payload = ytmusic.get_liked_songs(limit=liked_limit) or {}
    tracks = payload.get("tracks") or []
    print(f"[reverse] Loaded {len(tracks)} liked songs from YTMusic")

    for track in tracks:
        artists = track.get("artists") or []
        artist = str((artists[0] or {}).get("name", "")).strip() if artists else ""
        title = str(track.get("title", "")).strip()
        if not artist or not title:
            continue

        key = _track_key(artist, title)
        if key in historico_ids:
            continue

        spotify_track_id = None
        spotify_url_override = ""
        manual_link = manual_spotify_links.get(key, "").strip()
        if manual_link:
            spotify_track_id = _extract_spotify_track_id_from_url(manual_link)
            if spotify_track_id:
                spotify_url_override = manual_link
                print(f"[reverse] Using manual Spotify link from errors for: {artist} - {title}")
            else:
                print(
                    f"[reverse] Ignoring invalid manual Spotify link for {artist} - {title}: {manual_link}"
                )

        if not spotify_track_id:
            query = f"track:{title} artist:{artist}"
            results = spotify.search(q=query, type="track", limit=5)
            spotify_track_id = _pick_spotify_track_id(results, artist, title)

        if spotify_track_id:
            try:
                sp_track_info = spotify.track(spotify_track_id)
                spotify_artists_list = [a["name"] for a in sp_track_info.get("artists", [])]
                todos_artistas_album = [a["name"] for a in sp_track_info.get("album", {}).get("artists", [])]

                if todos_artistas_album:
                    spotify_album_artists_list = [todos_artistas_album[0]]
                else:
                    spotify_album_artists_list = (
                        [spotify_artists_list[0]] if spotify_artists_list else [artist]
                    )
            except Exception as e:
                print(f"[spotify] Erro ao obter detalhes da faixa (usando fallback): {e}")
                spotify_artists_list = [artist]
                spotify_album_artists_list = [artist]
            spotify_url = spotify_url_override or f"https://open.spotify.com/track/{spotify_track_id}"
            download_ok = True
            if spotiflac_enabled:
                ok, detail = _download_with_spotiflac(
                    spotify_url=spotify_url,
                    artist=artist,
                    title=title,
                    output_dir=spotiflac_output_dir,
                    command_template=spotiflac_command_template,
                    timeout_seconds=spotiflac_timeout_seconds,
                    services=spotiflac_services,
                    filename_format=spotiflac_filename_format,
                    use_artist_subfolders=spotiflac_use_artist_subfolders,
                    use_album_subfolders=spotiflac_use_album_subfolders,
                    loop_minutes=spotiflac_loop_minutes,
                    spotify_artists_list=spotify_artists_list,
                    spotify_album_artists_list=spotify_album_artists_list,
                )
                if not ok:
                    download_ok = False
                    _report_error(
                        backend_url,
                        artist,
                        title,
                        f"DOWNLOAD_SPOTIFLAC: {detail}",
                    )
            if not download_ok:
                # Keep out of historico so worker can retry later.
                if reverse_track_spacing_ms > 0:
                    time.sleep(reverse_track_spacing_ms / 1000.0)
                continue
            if add_to_playlist:
                spotify.playlist_add_items(spotify_playlist_id, [spotify_track_id])
            _add_historico(backend_url, key, artist, title)
            _clear_resolved_errors(backend_url, artist, title)
            historico_ids.add(key)
            print(f"[reverse] Processed: {artist} - {title}")
            if reverse_track_spacing_ms > 0:
                time.sleep(reverse_track_spacing_ms / 1000.0)
            continue

        _report_not_found(backend_url, artist, title)
        # Keep out of historico so worker can retry later.
        print(f"[reverse] Not found on Spotify (will retry): {artist} - {title}")
        if reverse_track_spacing_ms > 0:
            time.sleep(reverse_track_spacing_ms / 1000.0)
