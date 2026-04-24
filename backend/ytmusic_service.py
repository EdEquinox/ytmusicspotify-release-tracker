from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import HTTPException

try:
    from ytmusicapi import YTMusic
    from ytmusicapi.helpers import get_authorization, sapisid_from_cookie
except Exception:  # pragma: no cover - optional dependency in some environments
    YTMusic = None
    get_authorization = None
    sapisid_from_cookie = None


def _ytmusic_auth_targets() -> list[Path]:
    auth_path = Path(os.getenv("YTMUSIC_AUTH_FILE", "/data/ytmusic_auth.json")).resolve()
    reverse_auth_path = Path(
        os.getenv("REVERSE_YTMUSIC_AUTH_FILE", str(auth_path))
    ).resolve()
    targets = [auth_path]
    if reverse_auth_path not in targets:
        targets.append(reverse_auth_path)
    return targets


def _validate_ytmusic_auth_payload(auth_payload: dict, ytmusic_user: str | None = None) -> None:
    if YTMusic is None or get_authorization is None or sapisid_from_cookie is None:
        raise HTTPException(
            status_code=500,
            detail="ytmusicapi is not installed on backend. Add it to backend dependencies.",
        )

    if not isinstance(auth_payload, dict) or not auth_payload:
        raise ValueError("Auth payload must be a non-empty JSON object.")

    if "cookie" in auth_payload:
        cookie = str(auth_payload.get("cookie", "")).strip()
        origin = str(auth_payload.get("origin", "https://music.youtube.com")).strip()
        if not cookie:
            raise ValueError("Missing cookie in auth payload.")
        sapisid = sapisid_from_cookie(cookie)
        authorization = get_authorization(f"{sapisid} {origin}")
        headers = {
            "cookie": cookie,
            "origin": origin,
            "user-agent": str(auth_payload.get("user-agent", "")),
            "x-goog-authuser": str(auth_payload.get("x-goog-authuser", "0")),
            "x-goog-visitor-id": str(auth_payload.get("x-goog-visitor-id", "")),
            "authorization": authorization,
        }
        client = YTMusic(auth=headers, user=ytmusic_user or None)
        client.get_liked_songs(limit=1)
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=True, encoding="utf-8") as handle:
        handle.write(json.dumps(auth_payload, ensure_ascii=True))
        handle.flush()
        client = YTMusic(auth=handle.name, user=ytmusic_user or None)
        client.get_liked_songs(limit=1)


def _format_ytmusic_validate_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if (
        "sign in" in lowered
        or "twocolumnbrowseresultsrenderer" in lowered
        or "looking for what you’ve liked" in lowered
        or "looking for what you've liked" in lowered
    ):
        return (
            "Auth invalida/expirada para YTMusic (resposta de sign-in). "
            "Reexporta o JSON de browser auth e importa novamente em Settings."
        )
    return message
