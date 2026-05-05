from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from core.config import HISTORICO_FILE
from core.json_io import _read_json_list, _write_json_list
from models.schemas import HistoricoItem

router = APIRouter(tags=["historico"])


@router.get("/historico")
def list_historico() -> list[dict]:
    return _read_json_list(HISTORICO_FILE)


@router.post("/historico")
def create_historico(item: HistoricoItem) -> dict:
    historico = _read_json_list(HISTORICO_FILE)
    if any(str(existing.get("id")) == item.id for existing in historico):
        return {"status": "exists"}
    payload = item.model_dump()
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(UTC).isoformat()
    historico.append(payload)
    _write_json_list(HISTORICO_FILE, historico)
    return {"status": "added"}
