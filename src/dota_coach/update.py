from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import httpx

from dota_coach.config import APP_VERSION, DATA_DIR, GITHUB_REPO, UPDATE_CHANNEL_PATH, VERSION_PATH


ASSET_NAME = "DotaCoach.zip"
UA = "DotaCoach-Updater"


def local_version() -> str:
    for path in (VERSION_PATH, DATA_DIR / "version.json"):
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                ver = str(payload.get("version") or "").strip()
                if ver:
                    return ver
            except (OSError, json.JSONDecodeError):
                pass
    return APP_VERSION


def github_repo() -> str:
    env = (GITHUB_REPO or os.getenv("DOTA_COACH_GITHUB_REPO", "")).strip()
    if env:
        return env
    if UPDATE_CHANNEL_PATH.is_file():
        try:
            payload = json.loads(UPDATE_CHANNEL_PATH.read_text(encoding="utf-8"))
            return str(payload.get("github_repo") or "").strip()
        except (OSError, json.JSONDecodeError):
            return ""
    return ""


def parse_version(raw: str) -> tuple[int, ...]:
    text = raw.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or (0,))


def _latest_release(repo: str) -> dict[str, Any] | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers={"User-Agent": UA}) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        print(f"Обновление: не достучался до GitHub ({exc})")
        return None
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None
    return payload


def _asset_url(release: dict[str, Any]) -> str:
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        if name.lower() in {ASSET_NAME.lower(), "dotacoach-test.zip"}:
            return str(asset.get("browser_download_url") or "")
    assets = list(release.get("assets") or [])
    if len(assets) == 1:
        return str(assets[0].get("browser_download_url") or "")
    return ""


def _install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_apply_script(staging: Path, install_dir: Path, exe_name: str) -> Path:
    script = install_dir / "_apply_update.bat"
    src = str(staging)
    dst = str(install_dir)
    body = f"""@echo off
chcp 65001 >nul
ping 127.0.0.1 -n 3 >nul
taskkill /IM "{exe_name}" /F >nul 2>&1
robocopy "{src}" "{dst}" /E /IS /IT /NFL /NDL /NJH /NJS /R:2 /W:1
start "" "{dst}\\{exe_name}"
rmdir /S /Q "{src}"
del "%~f0"
"""
    script.write_text(body, encoding="utf-8")
    return script


def apply_release(release: dict[str, Any]) -> bool:
    url = _asset_url(release)
    if not url:
        print("Обновление: в релизе нет zip.")
        return False
    expected = ""
    for asset in release.get("assets") or []:
        if str(asset.get("browser_download_url") or "") == url:
            digest = str(asset.get("digest") or "")
            if digest.startswith("sha256:"):
                expected = digest.split(":", 1)[1].strip()
    install_dir = _install_dir()
    exe_name = Path(sys.executable).name if getattr(sys, "frozen", False) else "DotaCoach.exe"
    tmp = Path(tempfile.mkdtemp(prefix="dota_coach_upd_"))
    zip_path = tmp / ASSET_NAME
    print(f"Качаю {url}")
    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True, headers={"User-Agent": UA}) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with zip_path.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 64):
                        handle.write(chunk)
        if expected:
            got = _sha256(zip_path)
            if got.lower() != expected.lower():
                print("Обновление: хэш zip не совпал, отмена.")
                return False
        extract = tmp / "unpack"
        extract.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract)
        staging = tmp / "staging"
        inner = extract / "DotaCoach"
        if inner.is_dir():
            shutil.copytree(inner, staging)
        else:
            shutil.copytree(extract, staging)
        script = _write_apply_script(staging, install_dir, exe_name)
        subprocess.Popen(["cmd.exe", "/c", str(script)], close_fds=True)
        print("Обновление скачано, перезапускаюсь…")
        return True
    except (httpx.HTTPError, OSError, zipfile.BadZipFile) as exc:
        print(f"Обновление не удалось: {exc}")
        shutil.rmtree(tmp, ignore_errors=True)
        return False


def maybe_update(*, force: bool = False) -> bool:
    """True если процесс должен завершиться, чтобы применился апдейт."""
    if os.getenv("DOTA_COACH_NO_UPDATE", "").strip() in {"1", "true", "yes"}:
        return False
    if not force and not getattr(sys, "frozen", False):
        return False
    repo = github_repo()
    if not repo:
        return False
    current = local_version()
    release = _latest_release(repo)
    if not release:
        return False
    remote = str(release.get("tag_name") or release.get("name") or "").strip()
    if not remote:
        return False
    if parse_version(remote) <= parse_version(current):
        print(f"Версия {current}, обновлений нет.")
        return False
    print(f"Есть обновление {current} → {remote}")
    return apply_release(release)
