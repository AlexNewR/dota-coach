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
    OPENDOTA_MIN_MMR,
    OPENDOTA_MIN_RANK,
    OPENDOTA_PARSE_SCRAPER_ID,
    OPENDOTA_PUB_PAGES,
    OPENDOTA_REQUEST_GAP,
    PARSE_API_BASE,
    PARSE_API_KEY,
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
    # Без ключа дневной лимит жёсткий: короче backoff, быстрее fallback на cache/pubs.
    max_attempts = 6 if OPENDOTA_API_KEY else 4
    base_wait = 12 if OPENDOTA_API_KEY else 8
    wait_cap = 180 if OPENDOTA_API_KEY else 45
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code == 429:
                    body = (response.text or "").lower()
                    # Дневной лимит не лечится backoff'ом — сразу наружу для Parse/cache.
                    if "daily" in body or "limit exceeded" in body:
                        raise httpx.HTTPStatusError(
                            "OpenDota daily api limit exceeded",
                            request=response.request,
                            response=response,
                        )
                    wait = min(wait_cap, base_wait * (2**attempt))
                    print(f"OpenDota 429, sleep {wait}s…", flush=True)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            last_err = exc
            if "daily api limit" in str(exc).lower():
                raise
            time.sleep(OPENDOTA_REQUEST_GAP * (attempt + 2))
    if last_err:
        raise last_err
    raise httpx.HTTPStatusError("OpenDota rate limited", request=None, response=None)  # type: ignore[arg-type]

def _gap(multiplier: float = 1.0) -> None:
    base = OPENDOTA_REQUEST_GAP if OPENDOTA_API_KEY else max(1.8, OPENDOTA_REQUEST_GAP * 1.6)
    time.sleep(base * multiplier)


def _unwrap_parse_payload(payload: Any) -> Any:
    """Parse wraps OpenDota as {status, data: ...} sometimes nested twice."""
    cur: Any = payload
    for _ in range(4):
        if not isinstance(cur, dict):
            return cur
        if "rows" in cur or "match_id" in cur or "players" in cur:
            return cur
        nxt = cur.get("data")
        if nxt is None:
            return cur
        cur = nxt
    return cur


def parse_opendota_get(endpoint_name: str, params: dict[str, Any] | None = None) -> Any:
    """Вызов подписки Parse на OpenDota (обход локального daily limit)."""
    if not PARSE_API_KEY or not OPENDOTA_PARSE_SCRAPER_ID:
        raise RuntimeError("PARSE_API_KEY / OPENDOTA_PARSE_SCRAPER_ID not configured")
    url = f"{PARSE_API_BASE.rstrip('/')}/scraper/{OPENDOTA_PARSE_SCRAPER_ID}/{endpoint_name}"
    headers = {"X-API-Key": PARSE_API_KEY, "Accept": "application/json"}
    with httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0), follow_redirects=True) as client:
        response = client.get(url, params=params or {}, headers=headers)
        response.raise_for_status()
        return _unwrap_parse_payload(response.json())


def min_start_time(max_age_days: int | None = None) -> int:
    days = OPENDOTA_MAX_AGE_DAYS if max_age_days is None else max_age_days
    return int(time.time()) - max(1, int(days)) * 86400

def match_in_date_window(match: dict[str, Any], max_age_days: int | None = None) -> bool:
    start = int(match.get("start_time") or 0)
    if start <= 0:
        return False
    return start >= min_start_time(max_age_days)

def match_avg_mmr(match: dict[str, Any]) -> int | None:
    for key in ("avg_mmr", "average_mmr", "avg_rank_mmr"):
        val = match.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    # OpenDota убрал avg_mmr у public_matches; иногда остаётся computed_mmr у игроков.
    vals: list[float] = []
    for player in match.get("players") or []:
        raw = player.get("computed_mmr")
        if raw is None:
            continue
        try:
            vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    if vals:
        return int(sum(vals) / len(vals))
    return None


def match_avg_rank_tier(match: dict[str, Any]) -> int | None:
    for key in ("avg_rank_tier", "average_rank"):
        val = match.get(key)
        if val is not None:
            try:
                return int(float(val))
            except (TypeError, ValueError):
                continue
    ranks = [
        int(p["rank_tier"])
        for p in (match.get("players") or [])
        if p.get("rank_tier") is not None
    ]
    if not ranks:
        return None
    return sorted(ranks)[len(ranks) // 2]


def mmr_request_to_min_rank(min_mmr: int | None) -> int:
    """Грубый proxy: 7000+ MMR ≈ Immortal (80), когда avg_mmr недоступен."""
    threshold = OPENDOTA_MIN_MMR if min_mmr is None else min_mmr
    if threshold >= 7000:
        return 80
    if threshold >= 5500:
        return 75
    if threshold >= 4500:
        return 70
    return OPENDOTA_MIN_RANK


def match_mmr_ok(match: dict[str, Any], min_mmr: int | None = None) -> bool:
    threshold = OPENDOTA_MIN_MMR if min_mmr is None else min_mmr
    if threshold <= 0:
        return True
    avg = match_avg_mmr(match)
    if avg is not None:
        # computed_mmr иногда занижен относительно Immortal — не режем по нему вниз,
        # если лобби уже Immortal.
        if avg >= threshold:
            return True
    rank = match_avg_rank_tier(match)
    if rank is None:
        return avg is not None and avg >= threshold
    return rank >= mmr_request_to_min_rank(threshold)


def player_rank_ok(
    player: dict[str, Any],
    match: dict[str, Any],
    min_rank: int | None = None,
    allow_league: bool = True,
    min_mmr: int | None = None,
    accept_high_mmr_match: bool = False,
) -> bool:
    threshold = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    if threshold <= 0:
        return True
    leagueid = int(match.get("leagueid") or 0)
    if allow_league and leagueid > 0:
        return True
    if accept_high_mmr_match and match_mmr_ok(match, min_mmr=min_mmr):
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
    min_mmr: int | None = None,
    accept_high_mmr_match: bool = False,
    source: str = "opendota",
) -> list[dict[str, Any]]:
    if not match_in_date_window(match, max_age_days=max_age_days):
        return []
    players = list(match.get("players") or [])
    duration = int(match.get("duration") or 0)
    enemy_by_team: dict[bool, list[int]] = {True: [], False: []}
    for player in players:
        is_radiant = int(player.get("player_slot") or 0) < 128
        enemy_by_team[not is_radiant].append(int(player.get("hero_id") or 0))
    avg_mmr = match_avg_mmr(match)
    rows: list[dict[str, Any]] = []
    for player in players:
        hero_id = int(player.get("hero_id") or 0)
        if hero_id not in hero_ids:
            continue
        if not player_rank_ok(
            player,
            match,
            min_rank=min_rank,
            allow_league=allow_league,
            min_mmr=min_mmr,
            accept_high_mmr_match=accept_high_mmr_match,
        ):
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
                "source": source,
                "match_id": match.get("match_id"),
                "hero_id": hero_id,
                "lane_role": role if role else (lane_role or DEFAULT_LANE_ROLE),
                "duration": duration,
                "start_time": int(match.get("start_time") or 0),
                "leagueid": int(match.get("leagueid") or 0),
                "rank_tier": int(player.get("rank_tier") or 0) or None,
                "avg_mmr": avg_mmr,
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
    prefer_parse = bool(PARSE_API_KEY and OPENDOTA_PARSE_SCRAPER_ID and not OPENDOTA_API_KEY)
    if prefer_parse:
        try:
            match = parse_opendota_get("get_match", {"match_id": int(match_id)})
            if isinstance(match, dict) and match.get("match_id"):
                _save_match(match_id, match)
                return match
        except Exception as exc:  # noqa: BLE001
            print(f"OpenDota Parse get_match {match_id} failed: {exc}", flush=True)
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
            if "daily api limit" in str(exc).lower():
                break
            time.sleep(OPENDOTA_REQUEST_GAP * (attempt + 2))
    if PARSE_API_KEY and OPENDOTA_PARSE_SCRAPER_ID and not prefer_parse:
        try:
            match = parse_opendota_get("get_match", {"match_id": int(match_id)})
            if isinstance(match, dict) and match.get("match_id"):
                _save_match(match_id, match)
                return match
        except Exception as exc:  # noqa: BLE001
            print(f"OpenDota Parse get_match {match_id} failed: {exc}", flush=True)
    _ = last_err
    return None

def _explorer_rows(sql: str) -> list[dict[str, Any]]:
    # Без ключа OpenDota почти всегда daily-limit — сразу Parse, если есть.
    prefer_parse = bool(PARSE_API_KEY and OPENDOTA_PARSE_SCRAPER_ID and not OPENDOTA_API_KEY)
    if prefer_parse:
        try:
            payload = parse_opendota_get("get_explorer", {"sql": sql})
            if isinstance(payload, dict):
                return list(payload.get("rows") or [])
        except Exception as exc:  # noqa: BLE001
            print(f"OpenDota Parse explorer failed: {exc}", flush=True)
    try:
        payload = get_json("/explorer", {"sql": sql})
        return list((payload or {}).get("rows") or [])
    except httpx.HTTPError:
        pass
    if PARSE_API_KEY and OPENDOTA_PARSE_SCRAPER_ID and not prefer_parse:
        try:
            payload = parse_opendota_get("get_explorer", {"sql": sql})
            if isinstance(payload, dict):
                return list(payload.get("rows") or [])
        except Exception as exc:  # noqa: BLE001
            print(f"OpenDota Parse explorer failed: {exc}", flush=True)
    return []

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


def _public_summary_heroes(row: dict[str, Any]) -> set[int]:
    heroes: set[int] = set()
    for key in ("radiant_team", "dire_team"):
        team = row.get(key) or []
        if isinstance(team, str):
            continue
        for hid in team:
            try:
                heroes.add(int(hid))
            except (TypeError, ValueError):
                continue
    return heroes


def _public_row_mmr(row: dict[str, Any]) -> int | None:
    avg = match_avg_mmr(row)
    if avg is not None:
        return avg
    return None


def _public_row_rank_tier(row: dict[str, Any]) -> int | None:
    return match_avg_rank_tier(row)


def _hero_high_mmr_pub_ids_explorer(
    hero_id: int,
    limit: int,
    since: int,
    lane_role: int,
    min_mmr: int,
) -> list[tuple[int, int]]:
    """Immortal/high pub mid через explorer. (match_id, avg_rank_tier)."""
    out: list[tuple[int, int]] = []
    seen: set[int] = set()
    page = 100
    offset = 0
    min_tier = mmr_request_to_min_rank(min_mmr)
    while len(out) < limit:
        batch = min(page, limit - len(out))
        sql = (
            "SELECT player_matches.match_id, public_matches.avg_rank_tier "
            "FROM player_matches "
            "JOIN public_matches ON player_matches.match_id = public_matches.match_id "
            f"WHERE player_matches.hero_id = {int(hero_id)} "
            f"AND player_matches.lane_role = {int(lane_role)} "
            f"AND public_matches.avg_rank_tier >= {int(min_tier)} "
            f"AND public_matches.start_time >= {int(since)} "
            "ORDER BY public_matches.match_id DESC "
            f"LIMIT {batch} OFFSET {offset}"
        )
        rows = _explorer_rows(sql)
        if not rows:
            break
        for row in rows:
            mid = int(row.get("match_id") or 0)
            tier = int(float(row.get("avg_rank_tier") or 0))
            if mid and mid not in seen:
                seen.add(mid)
                out.append((mid, tier))
        offset += len(rows)
        if len(rows) < batch:
            break
        _gap(0.8)
    return out[:limit]


def scan_high_mmr_public_match_ids(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    min_mmr: int | None = None,
    min_rank: int | None = None,
    max_pages: int | None = None,
    max_candidates: int = 2500,
    max_age_days: int | None = None,
) -> list[int]:
    """Сканирует /publicMatches: Immortal+ (proxy для 7000+), с нашими героями."""
    mmr_floor = OPENDOTA_MIN_MMR if min_mmr is None else min_mmr
    rank_floor = max(
        80 if min_rank is None else int(min_rank),
        mmr_request_to_min_rank(mmr_floor),
    )
    pages = OPENDOTA_PUB_PAGES if max_pages is None else max_pages
    since = min_start_time(max_age_days)
    wanted = set(hero_ids)
    ids: list[int] = []
    seen: set[int] = set()
    cursor: int | None = None
    stale_pages = 0
    print(
        f"OpenDota pubs scan: min_mmr>={mmr_floor} (proxy rank>={rank_floor}), "
        f"pages<={pages}, heroes={sorted(wanted)}",
        flush=True,
    )
    for page in range(max(1, pages)):
        params: dict[str, Any] = {"min_rank": rank_floor}
        if cursor is not None:
            params["less_than_match_id"] = cursor
        try:
            batch = get_json("/publicMatches", params)
        except httpx.HTTPError as exc:
            print(f"OpenDota pubs scan stop: {exc}", flush=True)
            break
        if not batch:
            break
        page_hits = 0
        oldest = None
        for row in batch:
            mid = int(row.get("match_id") or 0)
            if not mid:
                continue
            oldest = mid if oldest is None else min(oldest, mid)
            start = int(row.get("start_time") or 0)
            if start and start < since:
                continue
            tier = _public_row_rank_tier(row)
            avg = _public_row_mmr(row)
            if avg is not None:
                if avg < mmr_floor:
                    continue
            elif tier is None or tier < rank_floor:
                continue
            if not (_public_summary_heroes(row) & wanted):
                continue
            if mid in seen:
                continue
            seen.add(mid)
            ids.append(mid)
            page_hits += 1
            if len(ids) >= max_candidates:
                print(f"OpenDota pubs scan: hit candidate cap {max_candidates}", flush=True)
                return ids
        if oldest is None or (cursor is not None and oldest >= cursor):
            stale_pages += 1
            if stale_pages >= 3:
                break
        else:
            stale_pages = 0
            cursor = oldest
        if (page + 1) % 10 == 0 or page_hits:
            print(
                f"OpenDota pubs scan: page {page + 1}/{pages}, "
                f"hits+={page_hits}, total={len(ids)}, cursor={cursor}",
                flush=True,
            )
        _gap(0.7)
    print(f"OpenDota pubs scan done: {len(ids)} candidate matches", flush=True)
    return ids


def collect_high_mmr_pubs(
    hero_ids: tuple[int, ...] = DEFAULT_HERO_IDS,
    per_hero: int = 400,
    lane_role: int = DEFAULT_LANE_ROLE,
    min_mmr: int | None = None,
    min_rank: int | None = None,
    max_age_days: int | None = None,
    max_pages: int | None = None,
    existing_keys: set[tuple[int, int]] | None = None,
) -> list[dict[str, Any]]:
    """Mid-ряды из high-MMR пабликов (не league)."""
    ensure_data_dirs()
    mmr_floor = OPENDOTA_MIN_MMR if min_mmr is None else min_mmr
    rank_floor = OPENDOTA_MIN_RANK if min_rank is None else min_rank
    age = OPENDOTA_MAX_AGE_DAYS if max_age_days is None else max_age_days
    since = min_start_time(age)
    by_hero: dict[int, int] = {hid: 0 for hid in hero_ids}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set(existing_keys or ())
    match_ids: list[int] = []
    seen_matches: set[int] = set()

    print(
        f"OpenDota pubs: Immortal/high mid proxy for mmr>={mmr_floor} "
        f"(rank>={mmr_request_to_min_rank(mmr_floor)}) heroes={list(hero_ids)}...",
        flush=True,
    )
    known_rank: dict[int, int] = {}
    # Explorer без API-ключа почти всегда 429 — сразу /publicMatches.
    if OPENDOTA_API_KEY:
        for hero_id in hero_ids:
            found = _hero_high_mmr_pub_ids_explorer(
                hero_id,
                limit=per_hero + 80,
                since=since,
                lane_role=lane_role,
                min_mmr=mmr_floor,
            )
            print(f"OpenDota pubs explorer hero {hero_id}: {len(found)} candidates", flush=True)
            for mid, tier in found:
                if tier:
                    known_rank[mid] = max(tier, known_rank.get(mid, 0))
                if mid not in seen_matches:
                    seen_matches.add(mid)
                    match_ids.append(mid)
            _gap(0.5)
    else:
        print("OpenDota pubs: no API key — skip explorer, use /publicMatches", flush=True)

    if (OPENDOTA_API_KEY and len(match_ids) < max(40, per_hero // 2)) or not OPENDOTA_API_KEY:
        scanned = scan_high_mmr_public_match_ids(
            hero_ids=hero_ids,
            min_mmr=mmr_floor,
            min_rank=max(rank_floor, mmr_request_to_min_rank(mmr_floor)),
            max_pages=max_pages,
            max_age_days=age,
        )
        for mid in scanned:
            if mid not in seen_matches:
                seen_matches.add(mid)
                match_ids.append(mid)

    match_ids = sorted(match_ids, key=lambda mid: 0 if _cached_match(mid) is not None else 1)
    print(f"OpenDota pubs collect: fetching {len(match_ids)} matches...", flush=True)
    for index, match_id in enumerate(match_ids):
        if all(by_hero[hid] >= per_hero for hid in hero_ids):
            break
        was_cached = _cached_match(match_id) is not None
        match = fetch_match(match_id, use_cache=True)
        if not was_cached:
            _gap()
        if match is None:
            continue
        # Только паблики: league уже покрыты explorer-путём.
        if int(match.get("leagueid") or 0) > 0:
            continue
        if match_avg_rank_tier(match) is None and match_id in known_rank:
            match = dict(match)
            match["avg_rank_tier"] = known_rank[match_id]
        if not match_mmr_ok(match, min_mmr=mmr_floor):
            continue
        take = extract_player_rows(
            match,
            hero_ids=hero_ids,
            lane_role=lane_role,
            min_rank=max(rank_floor, mmr_request_to_min_rank(mmr_floor)),
            max_age_days=age,
            allow_league=False,
            strict_lane=True,
            min_mmr=mmr_floor,
            accept_high_mmr_match=True,
            source="opendota_pub",
        )
        for row in take:
            hero_id = int(row["hero_id"])
            if by_hero.get(hero_id, 0) >= per_hero:
                continue
            key = (int(row["match_id"]), hero_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            by_hero[hero_id] = by_hero.get(hero_id, 0) + 1
        if (index + 1) % 25 == 0:
            print(
                f"OpenDota pubs: scanned {index + 1}/{len(match_ids)}, "
                f"rows={len(rows)} by_hero={by_hero}",
                flush=True,
            )
    for hero_id in hero_ids:
        print(f"OpenDota pubs hero {hero_id}: {by_hero[hero_id]} MID rows", flush=True)
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
