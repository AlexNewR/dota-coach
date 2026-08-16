from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Hint:
    kind: str
    title: str
    body: str
    severity: str = "info"
    key: str = ""
    ts: float = 0.0
    instead: str = ""
    enemy: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
