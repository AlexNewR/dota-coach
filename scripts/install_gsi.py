from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dota_coach.gsi.install_cfg import main  # noqa: E402

if __name__ == "__main__":
    main()
