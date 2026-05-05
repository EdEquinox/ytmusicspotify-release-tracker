from __future__ import annotations

from typing import Any


def _build_query(release: dict[str, Any]) -> str:
    name = str(release.get("name", "")).strip()
    artist_name = str(release.get("artist_name", "")).strip()
    return f"{name} {artist_name}".strip()


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().replace("-", " ").replace("_", " ").split())


def _is_close_title_match(left: str, right: str) -> bool:
    left_norm = _normalize_text(left)
    right_norm = _normalize_text(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    return left_norm in right_norm or right_norm in left_norm
