from __future__ import annotations
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP_NAME = "DotaCoach"
OUT_DIR = DIST / APP_NAME
ZIP_PATH = Path.home() / "Desktop" / "DotaCoach-test.zip"
RUNTIME_PROCESSED = (
    "farm_benchmarks.json",
    "death_benchmarks.json",
    "item_lookup.json",
    "hero_constants.json",
)
README = """Dota Coach — тестовая сборка
============================
1. Распакуй архив куда угодно.
2. Запусти ЗАПУСК.bat (или DotaCoach.exe).
3. В Steam у Dota 2 добавь параметр запуска:
   -gamestateintegration
4. Видео: Borderless Windowed.
5. Перезапусти Dota 2, зайди в матч (мид: LD / Io / KotL / Earth Spirit).
6. F8 — скрыть / показать окно поверх игры.
При запуске сам проверяет GitHub Releases и обновляется.
GSI ставится сам в cfg Dota (если Steam/Dota найдены).
Браузер не нужен. Python на ПК не нужен.
Если антивирус ругается на .exe — это обычный PyInstaller, добавь в исключения.
"""
BAT = r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Dota Coach
echo Запуск Dota Coach...
if not exist "DotaCoach.exe" (
  echo Не найден DotaCoach.exe рядом с этим файлом.
  pause
  exit /b 1
)
"DotaCoach.exe"
if errorlevel 1 (
  echo.
  echo Коуч завершился с ошибкой.
  pause
)
"""

def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)

def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        _run([sys.executable, "-m", "pip", "install", "pyinstaller"])

def _copy_runtime_data(target: Path) -> None:
    models = target / "data" / "models"
    processed = target / "data" / "processed"
    models.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    for name in ("item_mlp.npz", "item_vocab.json"):
        src = ROOT / "data" / "models" / name
        if not src.exists():
            raise FileNotFoundError(f"Нет модели: {src}")
        shutil.copy2(src, models / name)
    for name in RUNTIME_PROCESSED:
        src = ROOT / "data" / "processed" / name
        if src.exists():
            shutil.copy2(src, processed / name)
    data_root = target / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    for name in ("version.json", "update_channel.json"):
        src = ROOT / "data" / name
        if src.exists():
            shutil.copy2(src, data_root / name)

def build() -> Path:
    _ensure_pyinstaller()
    if DIST.exists():
        # не трогаем чужие артефакты целиком — чистим свою папку
        if OUT_DIR.exists():
            shutil.rmtree(OUT_DIR)
    DIST.mkdir(parents=True, exist_ok=True)
    # Windows: ; в --add-data
    sep = ";"
    add_data = [
        f"--add-data={ROOT / 'data' / 'models' / 'item_mlp.npz'}{sep}data/models",
        f"--add-data={ROOT / 'data' / 'models' / 'item_vocab.json'}{sep}data/models",
    ]
    for name in ("version.json", "update_channel.json"):
        src = ROOT / "data" / name
        if src.exists():
            add_data.append(f"--add-data={src}{sep}data")
    for name in RUNTIME_PROCESSED:
        src = ROOT / "data" / "processed" / name
        if src.exists():
            add_data.append(f"--add-data={src}{sep}data/processed")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        APP_NAME,
        "--paths",
        str(ROOT / "src"),
        "--console",
        "--noupx",
        "--collect-all",
        "numpy",
        "--collect-submodules",
        "uvicorn",
        "--collect-submodules",
        "fastapi",
        "--hidden-import",
        "numpy",
        "--hidden-import",
        "numpy._core",
        "--hidden-import",
        "numpy._core._multiarray_umath",
        "--hidden-import",
        "numpy.core._multiarray_umath",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.http.h11_impl",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        *add_data,
        str(ROOT / "scripts" / "run_coach.py"),
    ]
    _run(cmd)
    app_dir = DIST / APP_NAME
    if not (app_dir / f"{APP_NAME}.exe").exists():
        raise RuntimeError(f"PyInstaller не создал {app_dir / APP_NAME}.exe")
    # Проверка: без этого .pyd exe падает на чужом ПК
    umath = list(app_dir.rglob("_multiarray_umath*.pyd"))
    if not umath:
        raise RuntimeError("В сборке нет numpy._core._multiarray_umath — PyInstaller недособрал numpy")
    print(f"numpy umath: {umath[0].relative_to(app_dir)}", flush=True)
    # На всякий случай продублируем data рядом с exe (ROOT = папка exe)
    _copy_runtime_data(app_dir)
    (app_dir / "ЗАПУСК.bat").write_text(BAT, encoding="utf-8")
    (app_dir / "ЧИТАЙ.txt").write_text(README, encoding="utf-8")
    return app_dir

def zip_app(app_dir: Path) -> Path:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in app_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=str(Path(APP_NAME) / path.relative_to(app_dir)))
    return ZIP_PATH

def main() -> None:
    app_dir = build()
    zip_path = zip_app(app_dir)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Готово: {app_dir}")
    print(f"Архив: {zip_path} ({size_mb:.1f} MB)")
    print("Other PC: unzip, then ZAPUSK.bat")

if __name__ == "__main__":
    main()
