from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dota_coach.coach.engine import CoachEngine
from dota_coach.config import GSI_HOST, GSI_PORT, GSI_TOKEN, ensure_data_dirs
from dota_coach.data.heroes import load_hero_catalog
from dota_coach.gsi.normalize import GameState, normalize_gsi
from dota_coach.models.deaths import DeathBenchmarks
from dota_coach.models.farm import FarmBenchmarks
from dota_coach.models.items import load_item_model
from dota_coach.models.lookup import ItemLookup

app = FastAPI(title="Dota Coach")

_state: GameState | None = None
_engine: CoachEngine | None = None


def get_engine() -> CoachEngine:
    global _engine
    if _engine is None:
        ensure_data_dirs()
        load_hero_catalog()
        _engine = CoachEngine(
            farm=FarmBenchmarks(),
            deaths=DeathBenchmarks(),
            lookup=ItemLookup(),
            items=load_item_model(),
        )
    return _engine


def set_engine(engine: CoachEngine) -> None:
    global _engine
    _engine = engine


def get_snapshot() -> dict[str, Any]:
    return get_engine().snapshot(_state)


@app.post("/gsi")
async def gsi(request: Request) -> dict[str, str]:
    global _state
    payload: dict[str, Any] = await request.json()
    auth = payload.get("auth") or {}
    token = auth.get("token") if isinstance(auth, dict) else None
    if token and token != GSI_TOKEN:
        return {"status": "ignored"}
    state = normalize_gsi(payload)
    _state = state
    get_engine().update(state)
    return {"status": "ok"}


@app.get("/api/state")
async def api_state() -> dict[str, Any]:
    return get_snapshot()


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse({"status": "ok", "ui": "desktop"})


def main() -> None:
    get_engine()
    print(f"GSI: http://{GSI_HOST}:{GSI_PORT}/gsi")
    print("Интерфейс: python scripts\\run_coach.py")
    uvicorn.run(app, host=GSI_HOST, port=GSI_PORT, log_level="info")


if __name__ == "__main__":
    main()
