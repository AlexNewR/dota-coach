from __future__ import annotations

from dota_coach.config import ensure_data_dirs
from dota_coach.data.collect import load_player_rows
from dota_coach.data.synthetic import synthetic_dataset
from dota_coach.data.collect import load_protracker_heroes
from dota_coach.models.deaths import build_death_benchmarks, save_death_benchmarks
from dota_coach.models.farm import build_farm_benchmarks, save_farm_benchmarks
from dota_coach.models.items import save_item_model, train_item_model
from dota_coach.models.lookup import build_item_lookup, save_item_lookup


def train_all(
    min_opendota_rows: int = 40,
    allow_synthetic_nn: bool = False,
) -> dict[str, int | str | float | None]:
    ensure_data_dirs()
    all_rows = load_player_rows()
    # Explorer/pro + high-MMR pubs (source=opendota / opendota_pub).
    od_rows = [
        row
        for row in all_rows
        if str(row.get("source") or "").startswith("opendota")
    ]
    train_rows = od_rows
    if len(od_rows) < min_opendota_rows:
        if not allow_synthetic_nn:
            raise RuntimeError(
                f"Мало OpenDota-рядов для NN: {len(od_rows)} (нужно ≥ {min_opendota_rows}). "
                "Сначала: python scripts\\collect_data.py --opendota-primary --per-hero 400 --max-age-days 540"
            )
        train_rows = all_rows if all_rows else synthetic_dataset(load_protracker_heroes())
    # Farm/death/lookup: OpenDota (+pubs) + при необходимости синтетика для покрытия
    bench_rows = list(od_rows) if od_rows else list(train_rows)
    if len(bench_rows) < 80:
        bench_rows.extend(synthetic_dataset(load_protracker_heroes()))
    farm = build_farm_benchmarks(bench_rows)
    deaths = build_death_benchmarks(bench_rows)
    lookup = build_item_lookup(bench_rows)
    save_farm_benchmarks(farm)
    save_death_benchmarks(deaths)
    save_item_lookup(lookup)
    model, report = train_item_model(train_rows)
    save_item_model(model, report=report)
    return {
        "opendota_rows": len(od_rows),
        "train_rows": len(train_rows),
        "bench_rows": len(bench_rows),
        "farm_keys": len(farm),
        "death_keys": len(deaths),
        "lookup_keys": len(lookup),
        "item_classes": len(model.vocab.names),
        "val_top1": report.get("val_top1"),
        "val_top3": report.get("val_top3"),
        "samples": report.get("samples"),
    }
