from __future__ import annotations

import os
import time
from pathlib import Path

from ytmusicapi import YTMusic

from services.backend_client import _fetch_backend_settings
from sync.cycle import _sync_cycle


def _load_ytmusic_client(auth_file: str, ytmusic_user: str | None = None) -> YTMusic:
    print("[DEBUG] Inicializando YTMusic com Cookies (Browser Session)...")
    user = (ytmusic_user or "").strip() or None
    return YTMusic(auth=auth_file, user=user)


def main() -> None:
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")
    interval = int(os.getenv("WORKER_INTERVAL_SECONDS", "300"))
    backend_retry_seconds = 15
    idle_seconds = 20
    processed_seconds = 10
    playlist_id = ""
    auth_file = os.getenv("YTMUSIC_AUTH_FILE", "/data/ytmusic_auth.json").strip()
    env_ytmusic_user = os.getenv("YTMUSIC_USER", "").strip()
    last_effective_ytm_user = env_ytmusic_user

    print(
        f"Worker started. Backend: {backend_url}. Interval: {interval}s. "
        f"Auth file: {auth_file}. Playlist: {playlist_id}. User: {last_effective_ytm_user or 'default'}"
    )
    auth_path = Path(auth_file)
    if auth_path.is_file():
        print(f"[worker] Auth file OK ({auth_path.stat().st_size} bytes).")
    else:
        print(f"[worker] AVISO: ficheiro de auth não existe em {auth_path} — o YTMusic vai falhar.")
    if os.getenv("WORKER_DIAG", "").strip().lower() in ("1", "true", "yes", "on"):
        print(
            "[worker][diag] WORKER_DIAG=1: logs extra por release em sync/cycle.py; "
            "BACKEND_URL deve ser acessível deste contentor (ex. http://backend:8000)."
        )
    ytmusic = _load_ytmusic_client(auth_file, last_effective_ytm_user or None)

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
            effective_user = str(settings.get("ytmusic_user") or "").strip() or env_ytmusic_user
            if effective_user != last_effective_ytm_user:
                last_effective_ytm_user = effective_user
                ytmusic = _load_ytmusic_client(auth_file, effective_user or None)
                print(f"[worker] YTMusic user atualizado a partir das settings: {effective_user or 'default'}")
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
                ytmusic = _load_ytmusic_client(auth_file, last_effective_ytm_user or None)
                print("[worker] YTMusic auth reloaded. If 401 persists, reimport auth JSON in frontend.")
            except Exception as exc:
                print(f"[worker] Failed to reload YTMusic auth file: {exc}")
            time.sleep(backend_retry_seconds)
        elif cycle_result == "ytmusic_transport_error":
            transport_backoff = int(os.getenv("WORKER_TRANSPORT_BACKOFF_SECONDS", "300"))
            transport_backoff = max(transport_backoff, 30)
            print(
                f"[worker] Backoff {transport_backoff}s (YouTube a devolver HTML em vez de JSON nas pesquisas). "
                "Aumenta pausas nas Settings ou reimporta auth YTMusic; WORKER_TRANSPORT_BACKOFF_SECONDS no env ajusta isto."
            )
            time.sleep(transport_backoff)
        elif cycle_result == "idle":
            print(f"[worker] Sleeping {idle_seconds}s (queue idle)")
            time.sleep(idle_seconds)
        else:
            # After successful processing, recheck quickly for newly queued releases.
            print(f"[worker] Sleeping {processed_seconds}s (post-processing)")
            time.sleep(processed_seconds)


if __name__ == "__main__":
    main()
