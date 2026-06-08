from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from importlib.metadata import PackageNotFoundError, version

_PACKAGE = "spotiflac"
_last_check_monotonic = 0.0


def _auto_upgrade_enabled() -> bool:
    raw = os.getenv("REVERSE_SPOTIFLAC_PIP_AUTO_UPGRADE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _upgrade_interval_seconds() -> int:
    hours_raw = os.getenv("REVERSE_SPOTIFLAC_PIP_UPGRADE_INTERVAL_HOURS", "24").strip()
    try:
        hours = max(float(hours_raw), 0.25)
    except ValueError:
        hours = 24.0
    return int(hours * 3600)


def _installed_version() -> str | None:
    try:
        return version(_PACKAGE)
    except PackageNotFoundError:
        return None


def _pypi_latest_version() -> str | None:
    url = f"https://pypi.org/pypi/{_PACKAGE}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        latest = str(payload.get("info", {}).get("version", "")).strip()
        return latest or None
    except Exception as exc:
        print(f"[reverse] Falha ao consultar PyPI ({_PACKAGE}): {exc}")
        return None


def _is_newer(latest: str, installed: str) -> bool:
    try:
        from packaging.version import Version

        return Version(latest) > Version(installed)
    except Exception:
        return latest != installed


def _reload_spotiflac_modules() -> None:
    for name in list(sys.modules):
        lowered = name.lower()
        if lowered.startswith("spotiflac") or lowered == "spotiflac":
            del sys.modules[name]


def _run_pip_upgrade() -> tuple[bool, str | None]:
    before = _installed_version()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", _PACKAGE],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "pip upgrade timed out after 600s"
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail or f"pip exit code {result.returncode}"

    after = _installed_version()
    _reload_spotiflac_modules()
    if before and after and before != after:
        print(f"[reverse] spotiflac atualizado: {before} -> {after}")
    elif after:
        print(f"[reverse] spotiflac já na versão mais recente ({after})")
    else:
        print(f"[reverse] spotiflac instalado/atualizado via pip")
    return True, after


def maybe_upgrade_spotiflac(force: bool = False) -> None:
    global _last_check_monotonic

    if not _auto_upgrade_enabled():
        return

    now = time.monotonic()
    interval = _upgrade_interval_seconds()
    if not force and _last_check_monotonic and (now - _last_check_monotonic) < interval:
        return

    _last_check_monotonic = now
    installed = _installed_version()
    latest = _pypi_latest_version()
    if not latest:
        return

    if installed and not _is_newer(latest, installed):
        print(f"[reverse] spotiflac PyPI={latest}, instalado={installed} (sem update)")
        return

    if not installed:
        print(f"[reverse] spotiflac não encontrado; a instalar versão PyPI {latest}...")
    else:
        print(f"[reverse] spotiflac update disponível: {installed} -> {latest}")

    ok, detail = _run_pip_upgrade()
    if not ok:
        print(f"[reverse] Falha ao atualizar spotiflac: {detail}")
