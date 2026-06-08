from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from importlib.metadata import PackageNotFoundError, version

# 0.9.x has a bug: downloader reads opts.include_featuring but DownloadOptions lacks the field.
_DEFAULT_PIP_SPEC = "spotiflac>=0.8.7,<0.9.0"
_MAX_ALLOWED_VERSION = "0.9.0"
_MIN_ALLOWED_VERSION = "0.8.7"
_PACKAGE_NAMES = ("spotiflac", "SpotiFLAC")
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


def _pip_spec() -> str:
    return os.getenv("REVERSE_SPOTIFLAC_PIP_SPEC", _DEFAULT_PIP_SPEC).strip() or _DEFAULT_PIP_SPEC


def _installed_version() -> str | None:
    for name in _PACKAGE_NAMES:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return None


def _pypi_latest_allowed() -> str | None:
    url = f"https://pypi.org/pypi/spotiflac/json"
    try:
        from packaging.version import Version

        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        releases = payload.get("releases", {})
        max_v = Version(_MAX_ALLOWED_VERSION)
        min_v = Version(_MIN_ALLOWED_VERSION)
        allowed = [
            item
            for item in releases
            if Version(item) < max_v and Version(item) >= min_v
        ]
        if not allowed:
            return None
        return str(max(allowed, key=Version))
    except Exception as exc:
        print(f"[reverse] Falha ao consultar PyPI (spotiflac): {exc}")
        return None


def _is_newer(latest: str, installed: str) -> bool:
    try:
        from packaging.version import Version

        return Version(latest) > Version(installed)
    except Exception:
        return latest != installed


def _is_broken_version(installed: str) -> bool:
    try:
        from packaging.version import Version

        return Version(installed) >= Version(_MAX_ALLOWED_VERSION)
    except Exception:
        return False


def _reload_spotiflac_modules() -> None:
    for name in list(sys.modules):
        lowered = name.lower()
        if lowered.startswith("spotiflac") or lowered in {"spotiflac", "backend"}:
            del sys.modules[name]


def _run_pip_install() -> tuple[bool, str | None]:
    before = _installed_version()
    spec = _pip_spec()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir", spec],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "pip install timed out after 600s"
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
        print(f"[reverse] spotiflac na versão permitida ({after})")
    else:
        print("[reverse] spotiflac instalado/atualizado via pip")
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
    latest_allowed = _pypi_latest_allowed()
    if not latest_allowed:
        return

    if installed and _is_broken_version(installed):
        print(
            f"[reverse] spotiflac {installed} tem bug conhecido (include_featuring); "
            f"a instalar {latest_allowed} (<{_MAX_ALLOWED_VERSION})..."
        )
    elif installed and not _is_newer(latest_allowed, installed):
        print(
            f"[reverse] spotiflac PyPI max permitido={latest_allowed}, instalado={installed} (sem update)"
        )
        return
    elif not installed:
        print(f"[reverse] spotiflac não encontrado; a instalar {latest_allowed}...")
    else:
        print(f"[reverse] spotiflac update disponível: {installed} -> {latest_allowed}")

    ok, detail = _run_pip_install()
    if not ok:
        print(f"[reverse] Falha ao atualizar spotiflac: {detail}")
