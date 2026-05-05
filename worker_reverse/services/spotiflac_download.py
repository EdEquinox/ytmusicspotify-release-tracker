from __future__ import annotations

import os
import shlex
import subprocess

from SpotiFLAC import SpotiFLAC


def _fix_flac_artists_for_navidrome(
    before_snapshot: dict[str, tuple[int, int]],
    after_snapshot: dict[str, tuple[int, int]],
    spotify_artists_list: list[str],
    spotify_album_artists_list: list[str],
) -> None:
    new_files = set(after_snapshot) - set(before_snapshot)

    if not new_files:
        return

    try:
        from mutagen.flac import FLAC

        for filepath in new_files:
            if filepath.lower().endswith(".flac"):
                audio = FLAC(filepath)

                if "artist" in audio:
                    del audio["artist"]
                artists = spotify_artists_list
                if isinstance(artists, str):
                    artists = [artists]
                audio["artist"] = artists

                if "albumartist" in audio:
                    del audio["albumartist"]
                if "album artist" in audio:
                    del audio["album artist"]

                album_artists = spotify_album_artists_list
                if isinstance(album_artists, str):
                    album_artists = [album_artists]
                audio["albumartist"] = album_artists

                audio.save()

                print(f"[tag-fix] Injected: Artist {artists} | AlbumArtist {album_artists}")
    except ImportError:
        print("[tag-fix] mutagen library not found.")
    except Exception as e:
        print(f"[tag-fix] Mutagen error: {e}")


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
    spotify_album_artists_list: list[str],
) -> tuple[bool, str]:
    """First argument is the URL passed to SpotiFLAC (Spotify or Tidal track URL); CLI templates keep the name spotify_url."""
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
            _fix_flac_artists_for_navidrome(
                before_snapshot, after_snapshot, spotify_artists_list, spotify_album_artists_list
            )
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
    _fix_flac_artists_for_navidrome(
        before_snapshot, after_snapshot, spotify_artists_list, spotify_album_artists_list
    )
    return _enforce_flac_only(before_snapshot, after_snapshot)
