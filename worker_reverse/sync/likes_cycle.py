from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ytmusicapi import YTMusic

if TYPE_CHECKING:
    import spotipy

from services.backend_client import (
    _add_historico,
    _clear_resolved_errors,
    _extract_manual_spotify_links,
    _fetch_playlist_track_links,
    _list_errors,
    _list_historico_ids,
    _report_error,
    _report_not_found,
)
from services.matching import _track_key
from services.spotiflac_download import _download_with_spotiflac
from services.spotify_search import _extract_spotify_track_id_from_url, _pick_spotify_track_id
from services.tidal_resolve import resolve_tidal_url_with_fallback


def _sync_likes_cycle(
    backend_url: str,
    ytmusic: YTMusic,
    spotify: spotipy.Spotify | None,
    spotify_playlist_id: str,
    liked_limit: int,
    add_to_playlist: bool,
    tidal_only: bool,
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
    if not tidal_only:
        try:
            manual_spotify_links = _extract_manual_spotify_links(_list_errors(backend_url))
        except Exception as exc:
            print(f"[reverse] Failed to load manual Spotify links from errors: {exc}")
    try:
        playlist_links_by_video = _fetch_playlist_track_links(backend_url)
    except Exception as exc:
        print(f"[reverse] Failed to load playlist track links: {exc}")
        playlist_links_by_video = {}
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

        video_id = str(track.get("videoId") or "").strip()
        link_row = playlist_links_by_video.get(video_id) if video_id else None
        tidal_from_json = (str(link_row.get("tidal_url") or "").strip() if link_row else "") or ""
        tidal_resolved = resolve_tidal_url_with_fallback(
            backend_url,
            video_id,
            artist,
            title,
            playlist_links_by_video,
            persist_if_searched=bool(video_id),
        )
        if tidal_resolved and not tidal_from_json:
            print(f"[reverse] Tidal por pesquisa no backend (fallback) — {artist} - {title}")
        elif tidal_from_json:
            print(f"[reverse] Tidal em playlist_track_links.json (videoId={video_id or 'n/a'})")

        if tidal_only:
            if not tidal_resolved:
                print(
                    f"[reverse] tidal-only: sem URL Tidal (nem cache nem pesquisa Tidal no backend) — "
                    f"{artist} - {title}. Verifica sessao Tidal (Releases) e titulo/artista."
                )
                if reverse_track_spacing_ms > 0:
                    time.sleep(reverse_track_spacing_ms / 1000.0)
                continue
            if not spotiflac_enabled:
                print(
                    f"[reverse] tidal-only: ativa SpotiFLAC nas settings para descarregar "
                    f"— {artist} - {title}"
                )
                if reverse_track_spacing_ms > 0:
                    time.sleep(reverse_track_spacing_ms / 1000.0)
                continue
            tag_artists = [artist]
            tag_album_artists = [artist]
            ok, detail = _download_with_spotiflac(
                spotify_url=tidal_resolved,
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
                spotify_artists_list=tag_artists,
                spotify_album_artists_list=tag_album_artists,
            )
            if not ok:
                _report_error(backend_url, artist, title, f"DOWNLOAD_SPOTIFLAC: {detail}")
                if reverse_track_spacing_ms > 0:
                    time.sleep(reverse_track_spacing_ms / 1000.0)
                continue
            _add_historico(backend_url, key, artist, title)
            _clear_resolved_errors(backend_url, artist, title)
            historico_ids.add(key)
            print(f"[reverse] tidal-only: processado com Tidal local — {artist} - {title}")
            if reverse_track_spacing_ms > 0:
                time.sleep(reverse_track_spacing_ms / 1000.0)
            continue

        if spotify is None:
            print(
                "[reverse] ERRO: cliente Spotify ausente com «só Tidal» desligado nas settings "
                "(ou REVERSE_TIDAL_ONLY=0). Corrige OAuth Spotify ou ativa reverse_tidal_only / REVERSE_TIDAL_ONLY=1."
            )
            return

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

        spotify_artists_list = [artist]
        spotify_album_artists_list = [artist]
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

        spotify_url = spotify_url_override or (
            f"https://open.spotify.com/track/{spotify_track_id}" if spotify_track_id else ""
        )

        if not spotify_track_id and not tidal_resolved:
            _report_not_found(backend_url, artist, title)
            print(f"[reverse] Not found on Spotify e sem Tidal (cache/pesquisa) (will retry): {artist} - {title}")
            if reverse_track_spacing_ms > 0:
                time.sleep(reverse_track_spacing_ms / 1000.0)
            continue

        if not spotify_track_id and tidal_resolved and not spotiflac_enabled:
            print(
                f"[reverse] Ha URL Tidal (cache ou pesquisa) mas SpotiFLAC esta desligado; "
                f"a ignorar (ativa SpotiFLAC ou resolve Spotify): {artist} - {title}"
            )
            if reverse_track_spacing_ms > 0:
                time.sleep(reverse_track_spacing_ms / 1000.0)
            continue

        download_ok = not spotiflac_enabled
        if spotiflac_enabled:
            dl_url = tidal_resolved if tidal_resolved else spotify_url
            if not (dl_url or "").strip():
                download_ok = False
                _report_error(
                    backend_url,
                    artist,
                    title,
                    "DOWNLOAD_SPOTIFLAC: sem URL (nem Tidal em cache nem Spotify)",
                )
            else:
                ok, detail = _download_with_spotiflac(
                    spotify_url=dl_url,
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
            if reverse_track_spacing_ms > 0:
                time.sleep(reverse_track_spacing_ms / 1000.0)
            continue

        if add_to_playlist and spotify_track_id:
            spotify.playlist_add_items(spotify_playlist_id, [spotify_track_id])
        elif add_to_playlist and not spotify_track_id:
            print(
                "[reverse] add_to_playlist ignorado (sem ID Spotify); "
                "download pode ter usado só URL Tidal em cache."
            )
        _add_historico(backend_url, key, artist, title)
        _clear_resolved_errors(backend_url, artist, title)
        historico_ids.add(key)
        print(f"[reverse] Processed: {artist} - {title}")
        if reverse_track_spacing_ms > 0:
            time.sleep(reverse_track_spacing_ms / 1000.0)
