from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dota_coach.config import (  # noqa: E402
    OPENDOTA_MAX_AGE_DAYS,
    OPENDOTA_MIN_MMR,
    OPENDOTA_MIN_RANK,
    OPENDOTA_PER_HERO_DEFAULT,
    OPENDOTA_PUB_PAGES,
)
from dota_coach.data.collect import collect  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать данные для коуча / NN")
    parser.add_argument("--no-opendota", action="store_true", help="Не дополнять OpenDota")
    parser.add_argument("--opendota-matches", type=int, default=12, help="Случайный fallback или бюджет")
    parser.add_argument(
        "--opendota-primary",
        action="store_true",
        help="Основные player_rows только из OpenDota (по героям mid)",
    )
    parser.add_argument(
        "--per-hero",
        type=int,
        default=OPENDOTA_PER_HERO_DEFAULT,
        help=f"Сколько рядов на героя при --opendota-primary (default {OPENDOTA_PER_HERO_DEFAULT})",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=OPENDOTA_MAX_AGE_DAYS,
        help=f"Брать матчи не старше N дней (default {OPENDOTA_MAX_AGE_DAYS})",
    )
    parser.add_argument(
        "--min-rank",
        type=int,
        default=OPENDOTA_MIN_RANK,
        help=f"Минимальный rank_tier для pub (80=Immortal; default {OPENDOTA_MIN_RANK})",
    )
    parser.add_argument(
        "--min-mmr",
        type=int,
        default=OPENDOTA_MIN_MMR,
        help=f"Минимальный avg_mmr пабликов (default {OPENDOTA_MIN_MMR})",
    )
    parser.add_argument(
        "--pub-pages",
        type=int,
        default=OPENDOTA_PUB_PAGES,
        help=f"Сколько страниц /publicMatches сканировать (default {OPENDOTA_PUB_PAGES})",
    )
    parser.add_argument(
        "--no-pubs",
        action="store_true",
        help="Не сканировать high-MMR паблики (только explorer/pro + cache)",
    )
    parser.add_argument(
        "--append-pubs",
        action="store_true",
        help="Не трогать текущие rows: только докинуть mid из пабликов 7000+ MMR",
    )
    parser.add_argument(
        "--no-league",
        action="store_true",
        help="Не принимать league/pro матчи без rank_tier >= --min-rank",
    )
    args = parser.parse_args()
    summary = collect(
        use_opendota=not args.no_opendota,
        opendota_matches=args.opendota_matches,
        opendota_primary=args.opendota_primary,
        per_hero=args.per_hero,
        min_rank=args.min_rank,
        max_age_days=args.max_age_days,
        allow_league=not args.no_league,
        include_pubs=not args.no_pubs,
        min_mmr=args.min_mmr,
        pub_pages=args.pub_pages,
        append_pubs_only=args.append_pubs,
    )
    print(summary)


if __name__ == "__main__":
    main()
