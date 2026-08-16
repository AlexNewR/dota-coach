from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_root() -> Path:
    env = os.getenv("DOTA_COACH_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            exe_dir,
            exe_dir / "_internal",
            Path(getattr(sys, "_MEIPASS", exe_dir)),
        ]
        for candidate in candidates:
            if (candidate / "data" / "models" / "item_mlp.npz").is_file():
                return candidate
        return exe_dir
    return Path(__file__).resolve().parents[2]


ROOT = _resolve_root()


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"

GSI_HOST = os.getenv("DOTA_COACH_HOST", "127.0.0.1")
GSI_PORT = int(os.getenv("DOTA_COACH_PORT", "3000"))
GSI_TOKEN = os.getenv("DOTA_COACH_TOKEN", "dota_coach_local")
GSI_URI = f"http://{GSI_HOST}:{GSI_PORT}/gsi"

HINT_COOLDOWN_SECONDS = float(os.getenv("DOTA_COACH_HINT_COOLDOWN", "20"))
DEATH_HINT_COOLDOWN_SECONDS = float(os.getenv("DOTA_COACH_DEATH_COOLDOWN", "8"))
FARM_BELOW_P25_SECONDS = float(os.getenv("DOTA_COACH_FARM_SECONDS", "45"))
ITEM_HINT_GOLD_RATIO = 0.85

# Мид: Lone Druid, Io, Keeper of the Light, Earth Spirit
DEFAULT_HERO_IDS = (80, 91, 90, 107)
DEFAULT_LANE_ROLE = 2
PROTRACKER_HERO_SLUGS = {
    80: "Lone Druid",
    91: "Io",
    90: "Keeper of the Light",
    107: "Earth Spirit",
}

PROTRACKER_BASE = "https://dota2protracker.com"
PROTRACKER_REQUEST_GAP = 1.6

PARSE_API_KEY = os.getenv("PARSE_API_KEY", "")
PARSE_API_BASE = os.getenv("PARSE_API_BASE", "https://api.parse.bot")
PARSE_SCRAPER_ID = os.getenv(
    "PARSE_SCRAPER_ID",
    "66214c1a-6b6f-423b-9d88-1a64261b7b38",
)
# Подписка Parse на opendota.com API (explorer/match) — fallback без OPENDOTA_API_KEY.
OPENDOTA_PARSE_SCRAPER_ID = os.getenv(
    "OPENDOTA_PARSE_SCRAPER_ID",
    "842a36b5-bba8-420f-b477-bcba5896b5c9",
)

OPENDOTA_BASE = "https://api.opendota.com/api"
OPENDOTA_API_KEY = os.getenv("OPENDOTA_API_KEY", "")
# 80 = Immortal; 70–75 = Divine. League-матчи принимаются отдельно.
OPENDOTA_MIN_RANK = int(os.getenv("OPENDOTA_MIN_RANK", "70"))
# Паблики: целевой MMR (7000≈глубокий Immortal). OpenDota убрал avg_mmr —
# на практике фильтруем Immortal (rank_tier/avg_rank_tier >= 80).
OPENDOTA_MIN_MMR = int(os.getenv("OPENDOTA_MIN_MMR", "7000"))
# Сколько дней назад брать матчи (по start_time). Для редких mid (LD/Io) нужно шире.
OPENDOTA_MAX_AGE_DAYS = int(os.getenv("OPENDOTA_MAX_AGE_DAYS", "540"))
OPENDOTA_REQUEST_GAP = float(os.getenv("OPENDOTA_REQUEST_GAP", "1.15"))
OPENDOTA_PER_HERO_DEFAULT = int(os.getenv("OPENDOTA_PER_HERO", "400"))
# Сколько страниц /publicMatches сканировать при сборе high-MMR пабликов.
OPENDOTA_PUB_PAGES = int(os.getenv("OPENDOTA_PUB_PAGES", "120"))

FARM_BENCHMARKS_PATH = PROCESSED_DIR / "farm_benchmarks.json"
DEATH_BENCHMARKS_PATH = PROCESSED_DIR / "death_benchmarks.json"
ITEM_LOOKUP_PATH = PROCESSED_DIR / "item_lookup.json"
ITEM_MODEL_PATH = MODELS_DIR / "item_mlp.npz"
ITEM_VOCAB_PATH = MODELS_DIR / "item_vocab.json"
PLAYER_ROWS_PATH = RAW_DIR / "player_rows.jsonl"

APP_VERSION = os.getenv("DOTA_COACH_VERSION", "0.3.1")
GITHUB_REPO = os.getenv("DOTA_COACH_GITHUB_REPO", "")
UPDATE_CHANNEL_PATH = DATA_DIR / "update_channel.json"
VERSION_PATH = DATA_DIR / "version.json"


def ensure_data_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, MODELS_DIR, RAW_DIR / "matches"):
        path.mkdir(parents=True, exist_ok=True)
