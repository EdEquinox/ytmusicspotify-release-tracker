from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from config import DATA_DIR


def _ensure_data_file(path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text().strip():
        path.write_text("[]\n")


def _ensure_data_object_file(path: Path, default_payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists() or not path.read_text().strip():
        path.write_text(json.dumps(default_payload, ensure_ascii=True, indent=2) + "\n")


def _read_json_list(path: Path) -> list[dict]:
    _ensure_data_file(path)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in {path.name}") from exc

    if not isinstance(data, list):
        raise HTTPException(status_code=500, detail=f"{path.name} must contain a JSON array")
    return data


def _write_json_list(path: Path, payload: list[dict]) -> None:
    _ensure_data_file(path)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _read_json_object(path: Path, default_payload: dict) -> dict:
    _ensure_data_object_file(path, default_payload)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in {path.name}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail=f"{path.name} must contain a JSON object")
    return data


def _write_json_object(path: Path, payload: dict) -> None:
    _ensure_data_object_file(path, payload)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
