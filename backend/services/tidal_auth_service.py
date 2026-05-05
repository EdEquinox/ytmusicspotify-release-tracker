"""Sessão Tidal (OAuth device) persistida em ficheiro — mesmo fluxo que ``login_oauth`` no tidalapi."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import tidalapi

from core.config import TIDAL_SESSION_FILE

_lock = threading.Lock()
_login_thread: threading.Thread | None = None
_future_done: threading.Event = threading.Event()
_phase: str = "idle"
_last_error: str | None = None
# Reposto em cada start para o GET /device/status poder mostrar o link (polling sem depender só do POST).
_last_device_ui: dict[str, Any] = {}


def tidal_session_path() -> Path:
    return TIDAL_SESSION_FILE


def _session_file_exists() -> bool:
    return TIDAL_SESSION_FILE.is_file()


def load_tidal_session() -> tidalapi.Session | None:
    """Carrega sessão do disco; devolve ``None`` se não existir ou não estiver válida."""
    if not _session_file_exists():
        return None
    session = tidalapi.Session()
    try:
        if not session.load_session_from_file(TIDAL_SESSION_FILE):
            return None
        if session.check_login():
            return session
    except Exception:
        return None
    return None


def tidal_session_logged_in() -> bool:
    return load_tidal_session() is not None


def start_tidal_device_login() -> dict[str, Any]:
    """Inicia fluxo device (cliente embebido). Idempotente se já autenticado ou login em curso."""
    global _login_thread, _phase, _last_error, _future_done, _last_device_ui

    with _lock:
        if tidal_session_logged_in():
            return {"status": "already_logged_in"}

        if _login_thread is not None and _login_thread.is_alive():
            return {
                "status": "busy",
                "message": "Login Tidal já em progresso; aguarda ou consulta o estado.",
                **_last_device_ui,
            }

        session = tidalapi.Session()
        try:
            link_login = session.get_link_login()
        except Exception as exc:
            _phase = "failed"
            _last_error = str(exc)
            return {"status": "failed", "error": str(exc)}

        _phase = "waiting_user"
        _last_error = None
        _future_done.clear()
        _last_device_ui = {
            "verification_uri": link_login.verification_uri,
            "verification_uri_complete": link_login.verification_uri_complete,
            "user_code": link_login.user_code,
            "expires_in": int(link_login.expires_in),
        }

        def _run_login() -> None:
            global _phase, _last_error, _last_device_ui
            try:
                ok = session.process_link_login(link_login)
                if ok and session.check_login():
                    TIDAL_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
                    session.save_session_to_file(TIDAL_SESSION_FILE)
                    _phase = "success"
                else:
                    _phase = "failed"
                    _last_error = "Login Tidal não concluído."
            except Exception as exc:
                _phase = "failed"
                _last_error = str(exc)
            finally:
                _future_done.set()
                _last_device_ui = {}

        _login_thread = threading.Thread(target=_run_login, daemon=True)
        _login_thread.start()

        return {
            "status": "login_started",
            **_last_device_ui,
        }


def get_tidal_device_login_status() -> dict[str, Any]:
    """Estado do último fluxo device (para polling no frontend)."""
    if tidal_session_logged_in():
        return {"status": "logged_in"}

    with _lock:
        th = _login_thread
        phase = _phase
        err = _last_error
        done = _future_done.is_set()

    if th is not None and th.is_alive():
        out: dict[str, Any] = {"status": "pending", "phase": phase}
        out.update(_last_device_ui)
        return out

    if done:
        if tidal_session_logged_in():
            return {"status": "logged_in"}
        return {"status": "failed", "error": err or "unknown", "phase": phase}

    return {"status": "idle", "phase": phase}
