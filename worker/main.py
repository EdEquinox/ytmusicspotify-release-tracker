from __future__ import annotations

import os
import time

from ytmusicapi import YTMusic

from services.backend_client import _fetch_backend_settings
from sync.cycle import _sync_cycle


def _load_ytmusic_client(auth_file: str) -> YTMusic:
    print("[DEBUG] Inicializando YTMusic com Cookies (Browser Session)...")
    return YTMusic(auth=auth_file)


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
    ytmusic = _load_ytmusic_client(auth_file)

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
            print(
                f"[worker] Não foi possível obter /settings do API ({backend_url}). "
                f"Isto vem do container worker, não do log do uvicorn do backend. Erro: {exc}"
            )

        if not playlist_id:
            print(
                "[worker] playlist_id vazio (define na app em Definições / data/settings.json). "
                "A repetir após retry."
            )
            time.sleep(backend_retry_seconds)
            continue

        cycle_result = _sync_cycle(backend_url, ytmusic, playlist_id, strict_audio_only)
        if cycle_result == "backend_error":
            print(f"[worker] Sleeping {backend_retry_seconds}s (backend retry)")
            time.sleep(backend_retry_seconds)
        elif cycle_result == "ytmusic_auth_error":
            print("[worker] Attempting to reload YTMusic auth from file...")
            try:
                ytmusic = _load_ytmusic_client(auth_file)
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
