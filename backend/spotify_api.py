from __future__ import annotations

import json
import os
import time
from base64 import b64encode
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from config import ROOT_DIR, SPOTIFY_ACCOUNTS_URL
import state
from settings_service import _get_spotify_credentials


def _reverse_spotify_cache_path() -> Path:
    raw = os.getenv("REVERSE_SPOTIFY_CACHE_PATH", "/data/spotify_oauth_cache_reverse.json").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / raw
    return path


def _spotify_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: bytes | None = None,
    retries: int = 2,
) -> dict:
    now = time.time()
    if now < state._spotify_backoff_until:
        remaining = int(state._spotify_backoff_until - now)
        raise HTTPException(
            status_code=429,
            detail=f"Spotify rate limit cooldown active. Retry after {remaining}s.",
        )

    request = Request(url=url, method=method, headers=headers or {}, data=body)

    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                retry_after = int(exc.headers.get("Retry-After", "2"))
                state._spotify_backoff_until = max(
                    state._spotify_backoff_until, time.time() + max(retry_after, 1)
                )
                time.sleep(min(max(retry_after, 1), 3))
                continue
            if exc.code >= 500 and attempt < retries:
                time.sleep(1 + attempt)
                continue
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After", "unknown")
                retry_after_int = int(retry_after) if str(retry_after).isdigit() else 2
                state._spotify_backoff_until = max(
                    state._spotify_backoff_until, time.time() + max(retry_after_int, 1)
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Spotify rate limit reached (429). Retry-After: {retry_after}s.",
                ) from exc
            raise HTTPException(status_code=502, detail=f"Spotify request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt < retries:
                time.sleep(1 + attempt)
                continue
            raise HTTPException(status_code=502, detail=f"Spotify network error: {exc}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Spotify request failed: {exc}") from exc

    raise HTTPException(status_code=502, detail="Spotify request failed after retries")


def _get_spotify_access_token() -> str:
    if state._spotify_token and time.time() < state._spotify_token_expires_at:
        return state._spotify_token

    client_id, client_secret = _get_spotify_credentials()
    basic = b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    body = urlencode({"grant_type": "client_credentials"}).encode("utf-8")

    payload = _spotify_request(
        SPOTIFY_ACCOUNTS_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=body,
    )

    token = payload.get("access_token")
    expires_in = int(payload.get("expires_in", 3600))
    if not token:
        raise HTTPException(status_code=502, detail="Failed to obtain Spotify access token")

    state._spotify_token = token
    state._spotify_token_expires_at = time.time() + max(expires_in - 60, 60)
    return token
