from __future__ import annotations

import time

from dota_coach.coach.hints import Hint
from dota_coach.config import DEATH_HINT_COOLDOWN_SECONDS, HINT_COOLDOWN_SECONDS


class HintPolicy:
    def __init__(self) -> None:
        self.last_time = 0.0
        self.last_death_time = 0.0
        self.last_keys: dict[str, float] = {}
        self.history: list[Hint] = []

    def allow(self, hint: Hint, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        cooldown = DEATH_HINT_COOLDOWN_SECONDS if hint.kind == "death" else HINT_COOLDOWN_SECONDS
        last = self.last_death_time if hint.kind == "death" else self.last_time
        if now - last < cooldown:
            return False
        if now - self.last_keys.get(hint.key, 0.0) < cooldown * 2:
            return False
        return True

    def push(self, hint: Hint, now: float | None = None) -> Hint | None:
        now = time.time() if now is None else now
        if not self.allow(hint, now):
            return None
        hint.ts = now
        self.last_time = now
        if hint.kind == "death":
            self.last_death_time = now
        self.last_keys[hint.key] = now
        self.history.append(hint)
        self.history = self.history[-12:]
        return hint
