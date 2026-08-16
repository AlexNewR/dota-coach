from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_deploy import build, zip_app  # noqa: E402
from dota_coach.config import APP_VERSION  # noqa: E402

CHANNEL_PATH = ROOT / "data" / "update_channel.json"
VERSION_PATH = ROOT / "data" / "version.json"
RELEASE_ZIP = Path.home() / "Desktop" / "DotaCoach.zip"
REPO_NAME = "dota-coach"


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    gh = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    cmd = [gh, *args]
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT, check=False, text=True, capture_output=True)
    if check and result.returncode != 0:
        sys.stderr.write(result.stderr or result.stdout)
        raise SystemExit(result.returncode)
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_repo() -> str:
    status = _gh("auth", "status", check=False)
    if status.returncode != 0:
        sys.stderr.write(status.stderr or status.stdout)
        raise SystemExit("GitHub CLI не залогинен. В терминале: gh auth login")
    login = _gh("api", "user", "--jq", ".login").stdout.strip()
    if not login:
        raise SystemExit("Не удалось узнать GitHub login")
    repo = f"{login}/{REPO_NAME}"
    view = _gh("repo", "view", repo, check=False)
    if view.returncode != 0:
        created = _gh(
            "repo",
            "create",
            REPO_NAME,
            "--public",
            "--description",
            "Dota Coach — релизы для автообновления",
            check=False,
        )
        if created.returncode != 0:
            sys.stderr.write(created.stderr or created.stdout)
            raise SystemExit("Не смог создать репозиторий")
    _write_json(CHANNEL_PATH, {"github_repo": repo})
    return repo


def publish(version: str) -> None:
    tag = version if version.startswith("v") else f"v{version}"
    plain = tag.lstrip("v")
    repo = ensure_repo()
    _write_json(VERSION_PATH, {"version": plain})
    app_dir = build()
    zip_path = zip_app(app_dir)
    if RELEASE_ZIP.exists():
        RELEASE_ZIP.unlink()
    shutil.copy2(zip_path, RELEASE_ZIP)
    existing = _gh("release", "view", tag, "--repo", repo, check=False)
    if existing.returncode == 0:
        _gh("release", "delete", tag, "--repo", repo, "--yes", "--cleanup-tag")
    _gh(
        "release",
        "create",
        tag,
        str(RELEASE_ZIP),
        "--repo",
        repo,
        "--title",
        f"Dota Coach {plain}",
        "--notes",
        "При запуске коуч сам проверяет этот релиз и обновляется.",
    )
    print(f"Published {repo} {tag}")
    print("Other PC: install this zip once, then it self-updates.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать и выложить GitHub Release")
    parser.add_argument("--version", default=APP_VERSION)
    args = parser.parse_args()
    publish(args.version)


if __name__ == "__main__":
    main()
