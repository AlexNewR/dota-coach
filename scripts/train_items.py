from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dota_coach.models.train import train_all  # noqa: E402


def main() -> None:
    try:
        stats = train_all()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1) from exc
    print("Обучение завершено:", stats)


if __name__ == "__main__":
    main()
