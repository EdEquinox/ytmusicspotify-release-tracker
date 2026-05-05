from __future__ import annotations


def _is_ytmusic_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "401" in message
        or "unauthorized" in message
        or "authentication credential" in message
        or "login required" in message
    )
