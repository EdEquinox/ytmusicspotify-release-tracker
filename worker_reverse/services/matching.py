from __future__ import annotations

import re


def _normalize(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def _track_key(artist: str, title: str) -> str:
    return f"{_normalize(artist)}::{_normalize(title)}"
