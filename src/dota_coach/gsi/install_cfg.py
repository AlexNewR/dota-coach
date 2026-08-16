from __future__ import annotations

import re
import winreg
from pathlib import Path

from dota_coach.config import GSI_TOKEN, GSI_URI

CFG_NAME = "gamestate_integration_dota_coach.cfg"
CFG_BODY = f'''"Dota Coach"
{{
    "uri"               "{GSI_URI}"
    "timeout"           "5.0"
    "buffer"            "0.1"
    "throttle"          "0.1"
    "heartbeat"         "10.0"
    "data"
    {{
        "provider"      "1"
        "map"           "1"
        "player"        "1"
        "hero"          "1"
        "abilities"     "1"
        "items"         "1"
        "draft"         "1"
        "buildings"     "1"
    }}
    "auth"
    {{
        "token"         "{GSI_TOKEN}"
    }}
}}
'''


def _steam_path_from_registry() -> Path | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        value, _ = winreg.QueryValueEx(key, "SteamPath")
        path = Path(str(value))
        return path if path.exists() else None
    except OSError:
        return None


def _library_folders(steam: Path) -> list[Path]:
    folders = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if not vdf.exists():
        return folders
    text = vdf.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        folders.append(Path(match.group(1).replace("\\\\", "\\")))
    seen: list[Path] = []
    for folder in folders:
        if folder.exists() and folder not in seen:
            seen.append(folder)
    return seen


def find_dota_cfg_dir() -> Path | None:
    roots: list[Path] = []
    steam = _steam_path_from_registry()
    if steam:
        roots.extend(_library_folders(steam))
    roots.extend(
        [
            Path(r"C:\Program Files (x86)\Steam"),
            Path(r"C:\Program Files\Steam"),
            Path(r"D:\Steam"),
            Path(r"D:\SteamLibrary"),
        ]
    )
    rels = [
        Path("steamapps/common/dota 2 beta/game/dota/cfg"),
        Path("steamapps/common/dota 2 beta/dota/cfg"),
    ]
    seen: set[Path] = set()
    for root in roots:
        for rel in rels:
            cfg = (root / rel).resolve()
            if cfg in seen:
                continue
            seen.add(cfg)
            if (cfg.parent / "maps").exists() or cfg.exists():
                return cfg / "gamestate_integration"
    return None


def install_gsi_config(target: Path | None = None) -> Path:
    cfg_dir = target or find_dota_cfg_dir()
    if cfg_dir is None:
        raise FileNotFoundError(
            "Не нашёл папку Dota 2. Укажи путь вручную или поставь игру в Steam."
        )
    cfg_dir.mkdir(parents=True, exist_ok=True)
    path = cfg_dir / CFG_NAME
    path.write_text(CFG_BODY, encoding="utf-8")
    return path


def main() -> None:
    path = install_gsi_config()
    print(f"GSI-конфиг записан: {path}")
    print("В Steam у Dota 2 добавь параметр запуска: -gamestateintegration")
    print("Клиент должен быть в режиме Borderless Windowed.")


if __name__ == "__main__":
    main()
