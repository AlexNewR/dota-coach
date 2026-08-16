from __future__ import annotations
import json
import time
from typing import Any
from urllib.parse import urlencode
import httpx
from dota_coach.config import (
    DEFAULT_HERO_IDS,
    DEFAULT_LANE_ROLE,
    OPENDOTA_API_KEY,
    OPENDOTA_BASE,
    OPENDOTA_MAX_AGE_DAYS,
    OPENDOTA_MIN_RANK,
    OPENDOTA_REQUEST_GAP,
    RAW_DIR,
    ensure_data_dirs,
)
from dota_coach.constants import HEROES
MATCH_CACHE = RAW_DIR / "matches"

def _params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params = dict(extra or {})
    if OPENDOTA_API_KEY:
        params["api_key"] = OPENDOTA_API_KEY
    return params

def get_json(path: str, extra: dict[str, Any] | None = None) -> Any:
    url = f"{OPENDOTA_BASE}{path}"
    if extra or OPENDOTA_API_KEY:
        url = f"{url}?{urlencode(_params(extra))}"
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 429:
                    wait = 8 * (attempt + 1)
                    print(f"OpenDota 429, sleep {wait}s…", flush=True)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            last_err = exc
            time.sleep(OPENDOTA_REQUEST_GAP * (attempt + 2))
    if last_err:
        raise last_err
    raise httpx.HTTPStatusError("OpenDota rate limited", request=None, response=None)  # type: ignore[arg-type]

def _gap(multiplier: float = 1.0) -> None:
    base = OPENDOTA_REQUEST_GAP if OPENDOTA_API_KEY else max(1.8, OPENDOTA_REQUEST_GAP * 1.6)
    time.sleep(base * multiplier)

def min_start_time(max_age_days: int | None = None) -> int:
    days = OPENDOTA_MAX_AGE_DAYS if max_age_days is None else max_age_days
    return int(time.time()) - max(1, int(days)) * 86400

def match_in_date_window(match: dict[str, Any], max_age_days: int | None = None) -> bool:
    start = int(match.get("start_time") or 0)
    if start <= 0:
        return False
    return start >= min_start_time(max_age_days)

def player_rank_ok(
    player: dict[str, Any],
    match: dict[str, Any],
    min_rank: int | None = None,
    allow_league: bool = True,
) -> bool:
    threshold = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    if threshold <= 0:
        return True
    leagueid = int(match.get("leagueid") or 0)
    if allow_league and leagueid > 0:
        return True
    rank = player.get("rank_tier")
    if rank is None:
        return False
    return int(rank) >= threshold

def _death_times(players: list[dict[str, Any]], hero_id: int) -> list[int]:
    npc = HEROES.get(hero_id, {}).get("npc", "")
    short = npc.replace("npc_dota_hero_", "")
    times: list[int] = []
    for player in players:
        if int(player.get("hero_id") or 0) == hero_id:
            continue
        for event in player.get("kills_log") or []:
            key = str(event.get("key") or "")
            if short and short in key:
                times.append(int(event.get("time") or 0))
    return sorted(times)

def extract_player_rows(
    match: dict[str, Any],
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    lane_role: int | None = DEFAULT_LANE_ROLE,
    min_rank: int | None = None,
    max_age_days: int | None = None,
    allow_league: bool = True,
    strict_lane: bool = True,
) -> list[dict[str, Any]]:
    if not match_in_date_window(match, max_age_days=max_age_days):
        return []
    players = list(match.get("players") or [])
    duration = int(match.get("duration") or 0)
    enemy_by_team: dict[bool, list[int]] = {True: [], False: []}
    for player in players:
        is_radiant = int(player.get("player_slot") or 0) < 128
        enemy_by_team[not is_radiant].append(int(player.get("hero_id") or 0))
    rows: list[dict[str, Any]] = []
    for player in players:
        hero_id = int(player.get("hero_id") or 0)
        if hero_id not in hero_ids:
            continue
        if not player_rank_ok(player, match, min_rank=min_rank, allow_league=allow_league):
            continue
        role = int(player.get("lane_role") or 0)
        if lane_role is not None:
            if strict_lane:
                if role != lane_role:
                    continue
            elif role and role != lane_role:
                continue
        if not player.get("purchase_log"):
            continue
        if not player.get("gold_t") or not player.get("lh_t"):
            continue
        is_radiant = int(player.get("player_slot") or 0) < 128
        rows.append(
            {
                "source": "opendota",
                "match_id": match.get("match_id"),
                "hero_id": hero_id,
                "lane_role": role if role else (lane_role or DEFAULT_LANE_ROLE),
                "duration": duration,
                "start_time": int(match.get("start_time") or 0),
                "leagueid": int(match.get("leagueid") or 0),
                "rank_tier": int(player.get("rank_tier") or 0) or None,
                "gold_t": player.get("gold_t") or [],
                "lh_t": player.get("lh_t") or [],
                "xp_t": player.get("xp_t") or [],
                "purchase_log": player.get("purchase_log") or [],
                "deaths": int(player.get("deaths") or 0),
                "death_times": _death_times(players, hero_id),
                "enemy_heroes": enemy_by_team[is_radiant],
                "gpm": int(player.get("gold_per_min") or 0),
                "xpm": int(player.get("xp_per_min") or 0),
            }
        )
    return rows

def _cached_match(match_id: int) -> dict[str, Any] | None:
    path = MATCH_CACHE / f"{match_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

def _save_match(match_id: int, match: dict[str, Any]) -> None:
    ensure_data_dirs()
    (MATCH_CACHE / f"{match_id}.json").write_text(json.dumps(match), encoding="utf-8")

def fetch_match(match_id: int, use_cache: bool = True, retries: int = 3) -> dict[str, Any] | None:
    if use_cache:
        cached = _cached_match(match_id)
        if cached is not None:
            return cached
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            match = get_json(f"/matches/{match_id}")
            if isinstance(match, dict) and match.get("match_id"):
                _save_match(match_id, match)
                return match
            return None
        except httpx.HTTPError as exc:
            last_err = exc
            time.sleep(OPENDOTA_REQUEST_GAP * (attempt + 2))
    _ = last_err
    return None

def _explorer_rows(sql: str) -> list[dict[str, Any]]:
    try:
        payload = get_json("/explorer", {"sql": sql})
    except httpx.HTTPError:
        return []
    return list((payload or {}).get("rows") or [])

def _hero_match_ids_explorer_mid(hero_id: int, limit: int, since: int, lane_role: int) -> list[int]:
    """Про/parsed mid-матчи героя через explorer."""
    ids: list[int] = []
    seen: set[int] = set()
    page = 200
    offset = 0
    while len(ids) < limit:
        batch = min(page, limit - len(ids))
        sql = (
            "SELECT matches.match_id "
            "FROM matches "
            "JOIN player_matches ON matches.match_id = player_matches.match_id "
            f"WHERE player_matches.hero_id = {int(hero_id)} "
            f"AND player_matches.lane_role = {int(lane_role)} "
            f"AND matches.start_time >= {int(since)} "
            "ORDER BY matches.start_time DESC "
            f"LIMIT {batch} OFFSET {offset}"
        )
        rows = _explorer_rows(sql)
        if not rows:
            break
        for row in rows:
            mid = int(row.get("match_id") or 0)
            if mid and mid not in seen:
                seen.add(mid)
                ids.append(mid)
        offset += len(rows)
        if len(rows) < batch:
            break
        _gap(0.8)
    return ids[:limit]

def _hero_match_ids_player_matches_mid(hero_id: int, limit: int, lane_role: int) -> list[int]:
    """Доп. match_id из player_matches (без join) — больше покрытия, дату/ранг проверим при fetch."""
    sql = (
        "SELECT match_id FROM player_matches "
        f"WHERE hero_id = {int(hero_id)} AND lane_role = {int(lane_role)} "
        "ORDER BY match_id DESC "
        f"LIMIT {int(limit)}"
    )
    rows = _explorer_rows(sql)
    ids: list[int] = []
    seen: set[int] = set()
    for row in rows:
        mid = int(row.get("match_id") or 0)
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)
    return ids

def _mid_account_ids(hero_id: int, lane_role: int, limit: int = 40) -> list[int]:
    sql = (
        "SELECT account_id, COUNT(*) AS c FROM player_matches "
        f"WHERE hero_id = {int(hero_id)} AND lane_role = {int(lane_role)} "
        "AND account_id IS NOT NULL "
        "GROUP BY account_id ORDER BY c DESC "
        f"LIMIT {int(limit)}"
    )
    rows = _explorer_rows(sql)
    return [int(r["account_id"]) for r in rows if r.get("account_id")]

def _player_hero_match_ids(
    account_id: int,
    hero_id: int,
    since: int,
    min_rank: int,
    limit: int = 80,
) -> list[int]:
    try:
        payload = get_json(
            f"/players/{int(account_id)}/matches",
            {"hero_id": int(hero_id), "limit": int(limit)},
        )
    except httpx.HTTPError:
        return []
    ids: list[int] = []
    for row in payload or []:
        mid = int(row.get("match_id") or 0)
        start = int(row.get("start_time") or 0)
        if not mid or start < since:
            continue
        avg = int(row.get("average_rank") or 0)
        # average_rank часто есть в pub; 0 — не отсекаем (проверим rank_tier в матче)
        if avg and avg < min_rank:
            continue
        ids.append(mid)
    return ids

def hero_match_ids(
    hero_id: int,
    limit: int = 400,
    max_age_days: int | None = None,
    lane_role: int = DEFAULT_LANE_ROLE,
    min_rank: int | None = None,
    expand_players: bool = True,
) -> list[int]:
    """Собирает кандидатов mid: explorer + player_matches + матчи mid-аккаунтов."""
    since = min_start_time(max_age_days)
    threshold = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    ids: list[int] = []
    seen: set[int] = set()
    def _add(batch: list[int]) -> None:
        for mid in batch:
            if mid and mid not in seen:
                seen.add(mid)
                ids.append(mid)
    _add(_hero_match_ids_explorer_mid(hero_id, limit=limit, since=since, lane_role=lane_role))
    # Pub mid через аккаунты — только если про-пул не закрыл лимит (LD/Io)
    if expand_players and len(ids) < limit:
        accounts = _mid_account_ids(hero_id, lane_role=lane_role, limit=25)
        print(f"OpenDota hero {hero_id}: expand via {len(accounts)} mid accounts...", flush=True)
        for account_id in accounts:
            if len(ids) >= limit:
                break
            extra = _player_hero_match_ids(
                account_id,
                hero_id=hero_id,
                since=since,
                min_rank=threshold,
                limit=80,
            )
            _add(extra)
            _gap(0.5)
    return ids[:limit]

def collect_hero_opendota(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    per_hero: int = 400,
    lane_role: int = DEFAULT_LANE_ROLE,
    min_rank: int | None = None,
    max_age_days: int | None = None,
    allow_league: bool = True,
) -> list[dict[str, Any]]:
    """Строго mid (lane_role=2): без fallback на саппорт/офф/сейф."""
    ensure_data_dirs()
    rows: list[dict[str, Any]] = []
    seen_matches: set[int] = set()
    threshold = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    age = OPENDOTA_MAX_AGE_DAYS if max_age_days is None else max_age_days
    print(
        f"OpenDota filters: STRICT mid lane_role={lane_role}, "
        f"max_age_days={age}, min_rank={threshold}, allow_league={allow_league}, per_hero={per_hero}",
        flush=True,
    )
    for hero_id in hero_ids:
        got = 0
        skipped_date = 0
        skipped_rank = 0
        skipped_lane = 0
        skipped_parse = 0
        stagnant = 0
        match_ids = hero_match_ids(
            hero_id,
            limit=per_hero + 50,
            max_age_days=age,
            lane_role=lane_role,
            min_rank=threshold,
            expand_players=True,
        )
        match_ids = sorted(match_ids, key=lambda mid: 0 if _cached_match(mid) is not None else 1)
        print(f"OpenDota hero {hero_id}: {len(match_ids)} mid candidates...", flush=True)
        for index, match_id in enumerate(match_ids):
            if got >= per_hero:
                break
            if stagnant >= 250 and got > 0:
                print(f"OpenDota hero {hero_id}: stop early after {stagnant} misses (got {got})", flush=True)
                break
            if match_id in seen_matches:
                continue
            was_cached = _cached_match(match_id) is not None
            match = fetch_match(match_id, use_cache=True)
            if not was_cached:
                _gap()
            if match is None:
                skipped_parse += 1
                stagnant += 1
                continue
            seen_matches.add(match_id)
            if not match_in_date_window(match, max_age_days=age):
                skipped_date += 1
                stagnant += 1
                continue
            take = extract_player_rows(
                match,
                hero_ids=(hero_id,),
                lane_role=lane_role,
                min_rank=threshold,
                max_age_days=age,
                allow_league=allow_league,
                strict_lane=True,
            )
            if take:
                rows.append(take[0])
                got += 1
                stagnant = 0
                if got % 25 == 0:
                    print(f"OpenDota hero {hero_id}: {got}/{per_hero}...", flush=True)
            else:
                stagnant += 1
                players = [p for p in (match.get("players") or []) if int(p.get("hero_id") or 0) == hero_id]
                if not players:
                    skipped_parse += 1
                elif not any(int(p.get("lane_role") or 0) == lane_role for p in players):
                    skipped_lane += 1
                elif not any(
                    player_rank_ok(p, match, min_rank=threshold, allow_league=allow_league) for p in players
                ):
                    skipped_rank += 1
                else:
                    skipped_parse += 1
            if (index + 1) % 100 == 0:
                print(f"OpenDota hero {hero_id}: scanned {index + 1}/{len(match_ids)}, got {got}", flush=True)
        print(
            f"OpenDota hero {hero_id}: {got} MID rows "
            f"(skip date={skipped_date} lane={skipped_lane} rank={skipped_rank} other={skipped_parse}, "
            f"candidates={len(match_ids)})",
            flush=True,
        )
    return rows

def collect_from_match_cache(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    per_hero: int | None = None,
    lane_role: int = DEFAULT_LANE_ROLE,
    min_rank: int | None = None,
    max_age_days: int | None = None,
    allow_league: bool = True,
) -> list[dict[str, Any]]:
    """Строго mid-ряды из уже скачанных matches/*.json (без API)."""
    ensure_data_dirs()
    threshold = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    age = OPENDOTA_MAX_AGE_DAYS if max_age_days is None else max_age_days
    by_hero: dict[int, int] = {hid: 0 for hid in hero_ids}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    files = sorted(MATCH_CACHE.glob("*.json"))
    print(f"OpenDota cache rebuild: {len(files)} matches, strict mid...", flush=True)
    for path in files:
        try:
            match = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        mid = int(match.get("match_id") or 0)
        for hero_id in hero_ids:
            if per_hero is not None and by_hero[hero_id] >= per_hero:
                continue
            take = extract_player_rows(
                match,
                hero_ids=(hero_id,),
                lane_role=lane_role,
                min_rank=threshold,
                max_age_days=age,
                allow_league=allow_league,
                strict_lane=True,
            )
            if not take:
                continue
            key = (mid, hero_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(take[0])
            by_hero[hero_id] += 1
    for hero_id in hero_ids:
        print(f"OpenDota cache hero {hero_id}: {by_hero[hero_id]} MID rows", flush=True)
    return rows

def collect_opendota_fallback(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    max_matches: int = 20,
    min_rank: int | None = None,
    max_age_days: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    threshold = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    try:
        pro = get_json("/proMatches")
    except httpx.HTTPError:
        pro = []
    try:
        pubs = get_json("/publicMatches", {"min_rank": threshold})
    except httpx.HTTPError:
        pubs = []
    ids: list[int] = []
    for match in list(pro) + list(pubs):
        mid = int(match.get("match_id") or 0)
        start = int(match.get("start_time") or 0)
        if mid and mid not in seen:
            if start and start < min_start_time(max_age_days):
                continue
            seen.add(mid)
            ids.append(mid)
    for index, match_id in enumerate(ids[:max_matches]):
        match = fetch_match(match_id)
        if match is None:
            continue
        rows.extend(
            extract_player_rows(
                match,
                hero_ids=hero_ids,
                min_rank=threshold,
                max_age_days=max_age_days,
                strict_lane=True,
            )
        )
        if index + 1 < min(len(ids), max_matches):
            _gap()
    return rows
