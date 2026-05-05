from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

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


def _ytmusic_run_validation_probes(client: Any) -> None:
    """Match worker traffic: reverse uses liked library; forward worker uses search(albums|songs)."""
    client.get_liked_songs(limit=1)
    for filter_name in ("albums", "songs"):
        try:
            client.search("ytmusicapi", filter=filter_name, limit=1)
        except Exception as exc:
            raise RuntimeError(
                f"YTMusic search probe failed (filter={filter_name!r}). "
                f"This is the same call path as the main release worker. "
                f"Underlying error: {exc}"
            ) from exc


def _validate_ytmusic_auth_payload(auth_payload: dict, ytmusic_user: str | None = None) -> None:
    if YTMusic is None or get_authorization is None or sapisid_from_cookie is None:
        raise HTTPException(
            status_code=500,
            detail="ytmusicapi is not installed on backend. Add it to backend dependencies.",
        )

    if not isinstance(auth_payload, dict) or not auth_payload:
        raise ValueError("Auth payload must be a non-empty JSON object.")

    user = ytmusic_user or None

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
        client = YTMusic(auth=headers, user=user)
        _ytmusic_run_validation_probes(client)
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=True, encoding="utf-8") as handle:
        handle.write(json.dumps(auth_payload, ensure_ascii=True))
        handle.flush()
        client = YTMusic(auth=handle.name, user=user)
        _ytmusic_run_validation_probes(client)


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
    if "expecting value: line 1 column 1" in lowered:
        return (
            "O YTMusic devolveu uma resposta vazia ou em HTML. Isto frequentemente "
            "significa que o Cookie de Auth expirou. Reexporta e importa o JSON de auth novamente."
        )
    if "search probe" in lowered:
        return (
            "Falha no teste de pesquisa YTMusic (mesmo tipo de pedido que o worker de releases). "
            "Tipicamente HTML ou corpo vazio: rate limit, captcha, cookie a expirar, ou ytmusicapi desatualizada. "
            f"Detalhe: {message}"
        )
    return message
