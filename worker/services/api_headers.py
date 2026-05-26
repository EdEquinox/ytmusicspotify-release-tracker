from __future__ import annotations

import os


def api_headers() -> dict[str, str]:
    token = os.getenv("API_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
