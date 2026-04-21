from __future__ import annotations

import os
import re
import time
import json
import subprocess
import shlex
from typing import Any
import mutagen
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from ytmusicapi.helpers import get_authorization, sapisid_from_cookie
from SpotiFLAC import SpotiFLAC


def _normalize(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _track_key(artist: str, title: str) -> str:
    return f"{_normalize(artist)}::{_normalize(title)}"


def _is_ytmusic_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "401" in message
        or "unauthorized" in message
        or "authentication credential" in message
        or "login required" in message
    )


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


def _extract_spotify_track_id_from_url(url: str) -> str | None:
    value = url.strip()
    if not value:
        return None
    if "open.spotify.com/track/" in value:
        tail = value.split("open.spotify.com/track/", 1)[1]
        track_id = tail.split("?", 1)[0].split("/", 1)[0].strip()
        return track_id or None
    if value.startswith("spotify:track:"):
        track_id = value.split("spotify:track:", 1)[1].strip()
        return track_id or None
    return None


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


def _pick_spotify_track_id(results: dict[str, Any], artist: str, title: str) -> str | None:
    tracks = (((results or {}).get("tracks") or {}).get("items") or [])
    target_artist = _normalize(artist)
    target_title = _normalize(title)
    for item in tracks:
        result_title = _normalize(str(item.get("name", "")))
        if target_title and target_title not in result_title and result_title not in target_title:
            continue
        artists = item.get("artists") or []
        artist_names = [_normalize(str(row.get("name", ""))) for row in artists]
        if target_artist and any(target_artist in current for current in artist_names):
            return str(item.get("id", "")).strip() or None
    if tracks:
        return str(tracks[0].get("id", "")).strip() or None
    return None


def _build_spotify_client(
    backend_url: str,
    cache_path: str,
    default_client_id: str,
    default_client_secret: str,
    default_redirect_uri: str,
) -> tuple[spotipy.Spotify, SpotifyOAuth]:
    settings: dict[str, Any] = {}
    try:
        settings = _read_settings(backend_url)
    except Exception:
        # Backend may not be up yet; fallback to env values for startup resilience.
        settings = {}

    client_id = str(
        settings.get("spotify_oauth_client_id")
        or settings.get("spotify_client_id")
        or default_client_id
    ).strip()
    client_secret = str(settings.get("spotify_client_secret") or default_client_secret).strip()
    redirect_uri = str(
        settings.get("reverse_spotify_redirect_uri")
        or settings.get("spotify_oauth_redirect_uri")
        or default_redirect_uri
    ).strip()
    if not client_id or not client_secret:
        raise RuntimeError("Spotify OAuth credentials missing. Configure in Settings or env.")
    if not redirect_uri:
        raise RuntimeError("Spotify OAuth redirect URI missing. Configure in Settings or env.")
    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="playlist-modify-private playlist-modify-public",
        cache_path=cache_path,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager), auth_manager


def _load_ytmusic_client(auth_file: str) -> YTMusic:
    print(f"[DEBUG] Inicializando YTMusic com Cookies (Browser Session)...")
    # Tão simples quanto isto. auth_file agora será o caminho para o browser.json
    return YTMusic(auth=auth_file)

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
                # Extrai a lista perfeita de artistas (ex: ["Tyler, The Creator", "A$AP Rocky"])
                spotify_artists_list = [a["name"] for a in sp_track_info.get("artists", [])]
                todos_artistas_album = [a["name"] for a in sp_track_info.get("album", {}).get("artists", [])]
                
                # Guarda APENAS O PRIMEIRO (o dono do álbum) numa lista de 1 elemento
                if todos_artistas_album:
                    spotify_album_artists_list = [todos_artistas_album[0]]
                else:
                    # Fallback de segurança: usa o primeiro artista da própria música
                    spotify_album_artists_list = [spotify_artists_list[0]] if spotify_artists_list else [primary_artist]
            except Exception as e:
                print(f"[spotify] Erro ao obter detalhes da faixa (usando fallback): {e}")
                spotify_artists_list = [artist] # Fallback de segurança
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
                    spotify_artists_list=spotify_artists_list
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

def _fix_flac_artists_for_navidrome(before_snapshot, after_snapshot, spotify_artists_list: list) -> None:
    # A CORREÇÃO ESTÁ AQUI: set() extrai as chaves caso seja um dicionário
    new_files = set(after_snapshot) - set(before_snapshot)
    
    if not new_files:
        print("[tag-fix] ⚠️ Nenhum ficheiro novo detetado. A tag não foi alterada!")
        return

    try:
        from mutagen.flac import FLAC
        for filepath in new_files:
            if filepath.lower().endswith(".flac"):
                audio = FLAC(filepath)
                
                # 1. Destrói a tag antiga
                if "artist" in audio:
                    del audio["artist"]
                
                # 2. Garante o formato de lista
                if isinstance(spotify_artists_list, str):
                    spotify_artists_list = [spotify_artists_list]
                    
                # 3. Guarda a lista limpa do Spotify
                audio["artist"] = spotify_artists_list
                audio.save()
                
                print(f"[tag-fix] ✅ SUCESSO! Lista gravada no FLAC: {spotify_artists_list}")
    except ImportError:
        print("[tag-fix] ⚠️ Biblioteca 'mutagen' não encontrada.")
    except Exception as e:
        print(f"[tag-fix] ❌ Erro fatal no Mutagen: {e}")


def _fix_flac_artists_for_navidrome(before_snapshot, after_snapshot, spotify_artists_list: list, spotify_album_artists_list: list) -> None:
    new_files = set(after_snapshot) - set(before_snapshot)
    
    if not new_files:
        return

    try:
        from mutagen.flac import FLAC
        for filepath in new_files:
            if filepath.lower().endswith(".flac"):
                audio = FLAC(filepath)
                
                # --- 1. Corrigir o ARTISTA da Faixa ---
                if "artist" in audio:
                    del audio["artist"]
                if isinstance(spotify_artists_list, str):
                    spotify_artists_list = [spotify_artists_list]
                audio["artist"] = spotify_artists_list
                
                # --- 2. Corrigir o ARTISTA DO ÁLBUM ---
                # O FLAC usa 'albumartist', mas às vezes softwares usam 'album artist', limpamos ambos:
                if "albumartist" in audio:
                    del audio["albumartist"]
                if "album artist" in audio:
                    del audio["album artist"]
                    
                if isinstance(spotify_album_artists_list, str):
                    spotify_album_artists_list = [spotify_album_artists_list]
                audio["albumartist"] = spotify_album_artists_list
                
                audio.save()
                
                print(f"[tag-fix] ✅ Injetado: Artista {spotify_artists_list} | AlbumArtist {spotify_album_artists_list}")
    except ImportError:
        print("[tag-fix] ⚠️ Biblioteca 'mutagen' não encontrada.")
    except Exception as e:
        print(f"[tag-fix] ❌ Erro fatal no Mutagen: {e}")
        
def _download_with_spotiflac(
    spotify_url: str,
    artist: str,
    title: str,
    output_dir: str,
    command_template: str,
    timeout_seconds: int,
    services: list[str],
    filename_format: str,
    use_artist_subfolders: bool,
    use_album_subfolders: bool,
    loop_minutes: int,
    spotify_artists_list: list[str],
    correct_album_artists_list: list
) -> tuple[bool, str]:
    os.makedirs(output_dir, exist_ok=True)
    before_snapshot = _files_snapshot(output_dir)
    # Preferred path for recent spotiflac versions (Python API).
    try:
        SpotiFLAC(
            url=spotify_url,
            output_dir=output_dir,
            services=services,
            filename_format=filename_format,
            use_artist_subfolders=use_artist_subfolders,
            use_album_subfolders=use_album_subfolders,
            loop=max(loop_minutes, 0),
        )
        after_snapshot = _files_snapshot(output_dir)
        if before_snapshot != after_snapshot:
            _fix_flac_artists_for_navidrome(before_snapshot, after_snapshot, correct_artists_list, correct_album_artists_list)
            return _enforce_flac_only(before_snapshot, after_snapshot)
    except Exception as exc:
        # Fallback to CLI mode below for compatibility.
        api_error = str(exc)
    else:
        api_error = "spotiflac API finished but no file created/updated in output dir"
    try:
        command = command_template.format(
            spotify_url=spotify_url,
            output_dir=output_dir,
            artist=artist,
            title=title,
        )
    except KeyError as exc:
        return False, f"Invalid command template placeholder: {exc}"

    args = shlex.split(command)
    if not args:
        return False, "Empty spotiflac command"
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=max(timeout_seconds, 10),
            check=False,
        )
    except FileNotFoundError:
        return False, f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout_seconds}s"
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        return False, stderr or stdout or api_error or f"exit_code={result.returncode}"
    after_snapshot = _files_snapshot(output_dir)
    if before_snapshot == after_snapshot:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        detail = stderr or stdout or api_error or "spotiflac finished but no file created/updated in output dir"
        return False, detail
    _fix_flac_artists_for_navidrome(before_snapshot, after_snapshot, correct_artists_list, correct_album_artists_list)
    return _enforce_flac_only(before_snapshot, after_snapshot)


def _normalize_spotiflac_template(template: str) -> str:
    raw = (template or "").strip()
    if not raw:
        return 'spotiflac "{spotify_url}" "{output_dir}"'
    # Backward compatibility with old template used in previous versions.
    if "--output" in raw and "spotiflac download" in raw:
        return 'spotiflac "{spotify_url}" "{output_dir}"'
    return raw


def _files_snapshot(root_dir: str) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for current_root, _, files in os.walk(root_dir):
        for file_name in files:
            path = os.path.join(current_root, file_name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            snapshot[path] = (int(stat.st_size), int(stat.st_mtime))
    return snapshot


def _enforce_flac_only(
    before_snapshot: dict[str, tuple[int, int]],
    after_snapshot: dict[str, tuple[int, int]],
) -> tuple[bool, str]:
    changed_paths = [
        path
        for path, meta in after_snapshot.items()
        if before_snapshot.get(path) != meta
    ]
    if not changed_paths:
        return False, "no downloaded files detected"

    flac_paths = [path for path in changed_paths if path.lower().endswith(".flac")]
    non_flac_paths = [path for path in changed_paths if not path.lower().endswith(".flac")]

    for path in non_flac_paths:
        try:
            os.remove(path)
        except OSError:
            pass

    if not flac_paths:
        return False, "downloaded files were not FLAC (non-FLAC files removed)"
    return True, "ok"


def _ensure_spotify_token_non_interactive(auth_manager: SpotifyOAuth) -> bool:
    token_info = auth_manager.cache_handler.get_cached_token()
    if token_info:
        return True
    auth_url = auth_manager.get_authorize_url()
    print("[reverse] Spotify OAuth token not found in cache.")
    print(f"[reverse] Authorize once via this URL, then paste redirected URL into spotipy setup flow: {auth_url}")
    print("[reverse] After token is cached, worker will continue automatically.")
    return False


def main() -> None:
    backend_url = os.getenv("REVERSE_BACKEND_URL", "http://backend:8000").rstrip("/")
    ytmusic_auth_file = os.getenv("REVERSE_YTMUSIC_AUTH_FILE", "/data/ytmusic_auth.json").strip()
    ytmusic_user = os.getenv("REVERSE_YTMUSIC_USER", "").strip()
    spotify_playlist_id = ""
    spotify_client_id = ""
    spotify_client_secret = ""
    spotify_redirect_uri = ""
    spotify_cache_path = os.getenv("REVERSE_SPOTIFY_CACHE_PATH", "/data/spotify_oauth_cache_reverse.json").strip()
    poll_seconds = 300
    liked_limit = 100
    reverse_redirect_uri = spotify_redirect_uri
    add_to_playlist = True
    spotiflac_enabled = False
    spotiflac_output_dir = "/data/downloads"
    spotiflac_command_template = 'spotiflac "{spotify_url}" "{output_dir}"'
    spotiflac_command_template = _normalize_spotiflac_template(spotiflac_command_template)
    spotiflac_timeout_seconds = 600
    spotiflac_loop_minutes = 0
    reverse_track_spacing_ms = 0
    # Force strict service selection: only Tidal.
    spotiflac_services = ["tidal"]
    spotiflac_filename_format = os.getenv(
        "REVERSE_SPOTIFLAC_FILENAME_FORMAT",
        "{title} - {artist}",
    ).strip() or "{title} - {artist}"
    spotiflac_use_artist_subfolders = (
        os.getenv("REVERSE_SPOTIFLAC_USE_ARTIST_SUBFOLDERS", "true").strip().lower() != "false"
    )
    spotiflac_use_album_subfolders = (
        os.getenv("REVERSE_SPOTIFLAC_USE_ALBUM_SUBFOLDERS", "true").strip().lower() != "false"
    )

    print(
        f"[reverse] Worker started. Backend={backend_url} Playlist={spotify_playlist_id} "
        f"LikedLimit={liked_limit} Poll={poll_seconds}s"
    )

    ytmusic = _load_ytmusic_client(ytmusic_auth_file)
    spotify, spotify_auth_manager = _build_spotify_client(
        backend_url,
        spotify_cache_path,
        spotify_client_id,
        spotify_client_secret,
        reverse_redirect_uri,
    )

    while True:
        try:
            settings = _read_settings(backend_url)
            spotify_playlist_id = (
                str(settings.get("reverse_spotify_playlist_id") or spotify_playlist_id).strip()
            )
            liked_limit = max(int(settings.get("reverse_liked_limit", liked_limit)), 1)
            poll_seconds = max(int(settings.get("reverse_poll_seconds", poll_seconds)), 30)
            add_to_playlist = bool(settings.get("reverse_spotify_add_to_playlist", add_to_playlist))
            spotiflac_enabled = bool(settings.get("reverse_spotiflac_enabled", spotiflac_enabled))
            spotiflac_output_dir = str(settings.get("reverse_spotiflac_output_dir", spotiflac_output_dir)).strip() or "/data/downloads"
            spotiflac_command_template = (
                str(settings.get("reverse_spotiflac_command_template", spotiflac_command_template)).strip()
                or 'spotiflac "{spotify_url}" "{output_dir}"'
            )
            spotiflac_command_template = _normalize_spotiflac_template(spotiflac_command_template)
            spotiflac_timeout_seconds = max(
                int(settings.get("reverse_spotiflac_timeout_seconds", spotiflac_timeout_seconds)),
                10,
            )
            spotiflac_loop_minutes = max(
                int(settings.get("reverse_spotiflac_loop_minutes", spotiflac_loop_minutes)),
                0,
            )
            reverse_track_spacing_ms = max(
                int(settings.get("reverse_track_spacing_ms", reverse_track_spacing_ms)),
                0,
            )
            # Keep strict service selection independent from settings/env.
            spotiflac_services = ["tidal"]
            spotiflac_filename_format = (
                str(settings.get("reverse_spotiflac_filename_format", spotiflac_filename_format)).strip()
                or spotiflac_filename_format
            )
            spotiflac_use_artist_subfolders = bool(
                settings.get("reverse_spotiflac_use_artist_subfolders", spotiflac_use_artist_subfolders)
            )
            spotiflac_use_album_subfolders = bool(
                settings.get("reverse_spotiflac_use_album_subfolders", spotiflac_use_album_subfolders)
            )
            configured_redirect = str(settings.get("reverse_spotify_redirect_uri", "")).strip()
            if configured_redirect and configured_redirect != reverse_redirect_uri:
                reverse_redirect_uri = configured_redirect
                spotify, spotify_auth_manager = _build_spotify_client(
                    backend_url,
                    spotify_cache_path,
                    spotify_client_id,
                    spotify_client_secret,
                    reverse_redirect_uri,
                )
            if add_to_playlist and not spotify_playlist_id:
                raise RuntimeError("Missing reverse_spotify_playlist_id in Settings (or REVERSE_SPOTIFY_PLAYLIST_ID env).")
            if not _ensure_spotify_token_non_interactive(spotify_auth_manager):
                time.sleep(poll_seconds)
                continue
            _sync_likes_cycle(
                backend_url=backend_url,
                ytmusic=ytmusic,
                spotify=spotify,
                spotify_playlist_id=spotify_playlist_id,
                liked_limit=liked_limit,
                add_to_playlist=add_to_playlist,
                spotiflac_enabled=spotiflac_enabled,
                spotiflac_output_dir=spotiflac_output_dir,
                spotiflac_command_template=spotiflac_command_template,
                spotiflac_timeout_seconds=spotiflac_timeout_seconds,
                spotiflac_services=spotiflac_services,
                spotiflac_filename_format=spotiflac_filename_format,
                spotiflac_use_artist_subfolders=spotiflac_use_artist_subfolders,
                spotiflac_use_album_subfolders=spotiflac_use_album_subfolders,
                reverse_track_spacing_ms=reverse_track_spacing_ms,
                spotiflac_loop_minutes=spotiflac_loop_minutes,
                correct_album_artists_list=spotify_album_artists_list
            )
        except Exception as exc:
            print(f"[reverse] Sync cycle failed: {exc}")
            if _is_ytmusic_auth_error(exc):
                print("[reverse] Attempting to reload YTMusic auth from file...")
                try:
                    ytmusic = _load_ytmusic_client(ytmusic_auth_file)
                    print(
                        "[reverse] YTMusic auth reloaded. If 401 persists, reimport auth JSON in frontend."
                    )
                except Exception as reload_exc:
                    print(f"[reverse] Failed to reload YTMusic auth file: {reload_exc}")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
