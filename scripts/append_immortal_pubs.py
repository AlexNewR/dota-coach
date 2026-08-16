from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dota_coach.config import DEFAULT_HERO_IDS, PLAYER_ROWS_PATH, RAW_DIR, ensure_data_dirs
from dota_coach.data.collect import _merge_rows, _row_keys, _write_jsonl
from dota_coach.data.opendota import extract_player_rows, fetch_match, match_mmr_ok


def _load_json_array(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON array in {path}")
    return json.loads(text[start : end + 1])


def collect_candidates(seed_pages: list[Path], extra_pages: int = 20) -> list[int]:
    wanted = set(DEFAULT_HERO_IDS)
    cands: list[int] = []
    seen: set[int] = set()
    cursor: int | None = None

    def _ingest(batch: list[dict]) -> None:
        nonlocal cursor
        for row in batch:
            mid = int(row.get("match_id") or 0)
            if not mid:
                continue
            cursor = mid if cursor is None else min(cursor, mid)
            tier = int(float(row.get("avg_rank_tier") or 0))
            team = set(row.get("radiant_team") or []) | set(row.get("dire_team") or [])
            # /publicMatches?min_rank=80 уже high-skill; avg часто ~75 даже в Immortal-пуле.
            if not (team & wanted):
                continue
            if tier and tier < 70:
                continue
            if mid in seen:
                continue
            seen.add(mid)
            cands.append(mid)

    for path in seed_pages:
        if path.exists():
            batch = _load_json_array(path)
            print(f"seed {path.name}: {len(batch)} rows", flush=True)
            _ingest(batch)
    print(f"candidates after seeds: {len(cands)}", flush=True)

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        rate_hits = 0
        for page in range(extra_pages):
            if cursor is None:
                break
            time.sleep(4.0)
            url = f"https://api.opendota.com/api/publicMatches?min_rank=80&less_than_match_id={cursor}"
            response = client.get(url)
            print(f"page {page + 1}: HTTP {response.status_code}", flush=True)
            if response.status_code == 429:
                rate_hits += 1
                if rate_hits >= 2:
                    print("rate limited — continue with seed candidates", flush=True)
                    break
                time.sleep(60)
                continue
            rate_hits = 0
            if response.status_code != 200:
                break
            batch = response.json()
            if not batch:
                break
            before = len(cands)
            _ingest(batch)
            print(f"  +{len(cands) - before} hits, total={len(cands)}, cursor={cursor}", flush=True)

    ensure_data_dirs()
    out = RAW_DIR / "pub_candidates.json"
    out.write_text(json.dumps(cands), encoding="utf-8")
    print(f"saved {len(cands)} -> {out}", flush=True)
    return cands


def append_rows(match_ids: list[int], min_mmr: int = 7000, per_hero: int = 150) -> dict:
    existing: list[dict] = []
    if PLAYER_ROWS_PATH.exists():
        for line in PLAYER_ROWS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.append(json.loads(line))
    by_hero = {hid: 0 for hid in DEFAULT_HERO_IDS}
    for row in existing:
        hid = int(row.get("hero_id") or 0)
        if hid in by_hero:
            by_hero[hid] += 1
    seen = _row_keys(existing)
    new_rows: list[dict] = []
    print(f"fetching up to {len(match_ids)} matches; existing={len(existing)}", flush=True)
    for index, match_id in enumerate(match_ids):
        if all(by_hero[hid] >= per_hero * 2 for hid in DEFAULT_HERO_IDS):
            # already have enough overall; still allow pubs to fill thin heroes
            thin = [hid for hid in DEFAULT_HERO_IDS if by_hero[hid] < per_hero]
            if not thin:
                break
        match = fetch_match(match_id, use_cache=True, allow_parse=False)
        time.sleep(1.6)
        if match is None or int(match.get("leagueid") or 0) > 0:
            continue
        if not match_mmr_ok(match, min_mmr=min_mmr):
            continue
        take = extract_player_rows(
            match,
            hero_ids=DEFAULT_HERO_IDS,
            min_rank=70,
            allow_league=False,
            strict_lane=True,
            min_mmr=min_mmr,
            accept_high_mmr_match=True,
            source="opendota_pub",
        )
        for row in take:
            hid = int(row["hero_id"])
            key = (int(row["match_id"]), hid)
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(row)
            by_hero[hid] = by_hero.get(hid, 0) + 1
        if (index + 1) % 10 == 0:
            print(f"scanned {index + 1}/{len(match_ids)} new={len(new_rows)} by_hero={by_hero}", flush=True)

    merged = _merge_rows(existing, new_rows)
    _write_jsonl(PLAYER_ROWS_PATH, merged)
    summary = {
        "existing": len(existing),
        "added": len(new_rows),
        "total": len(merged),
        "by_hero": by_hero,
    }
    print(summary, flush=True)
    return summary


def main() -> None:
    seeds = [
        Path(r"C:\Users\alwexn\.cursor\projects\c-Users-alwexn-Desktop-dota-train\agent-tools\ce858eaa-2969-4bae-9c73-2e41b4b63d4c.txt"),
        Path(r"C:\Users\alwexn\.cursor\projects\c-Users-alwexn-Desktop-dota-train\agent-tools\7a68f7d3-6655-4af1-8205-6631e2523c45.txt"),
    ]
    cands = collect_candidates(seeds, extra_pages=8)
    if not cands:
        print("no candidates", flush=True)
        return
    append_rows(cands, min_mmr=7000, per_hero=200)


if __name__ == "__main__":
    main()
