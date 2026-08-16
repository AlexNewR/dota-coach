from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from dota_coach.config import (
    DEFAULT_HERO_IDS,
    DEFAULT_LANE_ROLE,
    ITEM_HINT_GOLD_RATIO,
    ITEM_MODEL_PATH,
    ITEM_VOCAB_PATH,
    PROCESSED_DIR,
)
from dota_coach.constants import (
    BOOT_ITEMS,
    BOOT_LATE_MINUTE,
    INVENTORY_SLOT_LIMIT,
    ITEM_COSTS,
    is_finished_item,
    is_upgrade_of_owned,
    item_allowed_for_hero,
    item_takes_inventory_slot,
    normalize_item_name,
    owned_boots,
)
from dota_coach.gsi.normalize import GameState

MAX_HERO = 160
HIDDEN1 = 128
HIDDEN2 = 64


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=-1, keepdims=True)


class ItemVocab:
    def __init__(self, names: list[str]) -> None:
        self.names = names
        self.index = {name: i for i, name in enumerate(names)}

    def encode(self, name: str) -> int | None:
        return self.index.get(name)

    def to_json(self) -> dict[str, Any]:
        return {"names": self.names}

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "ItemVocab":
        return cls(list(payload["names"]))


def build_vocab(rows: list[dict[str, Any]], min_count: int = 3) -> ItemVocab:
    counts: dict[str, int] = {}
    for row in rows:
        for event in row.get("purchase_log") or []:
            name = normalize_item_name(event.get("key"))
            if name:
                counts[name] = counts.get(name, 0) + 1
    names = [
        name
        for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if count >= min_count and is_finished_item(name)
    ]
    if not names:
        names = sorted(ITEM_COSTS)
    return ItemVocab(names)


def feature_vector(
    hero_id: int,
    role: int,
    minute: float,
    gold: float,
    net_worth: float,
    level: float,
    inventory: list[str],
    enemy_heroes: list[int],
    vocab: ItemVocab,
) -> np.ndarray:
    hero = np.zeros(len(DEFAULT_HERO_IDS), dtype=np.float32)
    if hero_id in DEFAULT_HERO_IDS:
        hero[DEFAULT_HERO_IDS.index(hero_id)] = 1.0
    role_vec = np.zeros(5, dtype=np.float32)
    role_vec[max(0, min(4, role - 1))] = 1.0
    items = np.zeros(len(vocab.names), dtype=np.float32)
    for name in inventory:
        idx = vocab.encode(name)
        if idx is not None:
            items[idx] = 1.0
    enemies = np.zeros(MAX_HERO, dtype=np.float32)
    for hid in enemy_heroes:
        if 0 < hid < MAX_HERO:
            enemies[hid] = 1.0
    numeric = np.array(
        [
            minute / 40.0,
            gold / 5000.0,
            net_worth / 20000.0,
            level / 25.0,
            len(inventory) / float(INVENTORY_SLOT_LIMIT),
        ],
        dtype=np.float32,
    )
    return np.concatenate([hero, role_vec, numeric, items, enemies])


def build_dataset(rows: list[dict[str, Any]], vocab: ItemVocab) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Возвращает X, y, match_ids (для split по матчу)."""
    xs: list[np.ndarray] = []
    ys: list[int] = []
    match_ids: list[int] = []
    for row in rows:
        hero_id = int(row.get("hero_id") or 0)
        if hero_id not in DEFAULT_HERO_IDS:
            continue
        role = int(row.get("lane_role") or DEFAULT_LANE_ROLE)
        gold_t = list(row.get("gold_t") or [])
        owned: list[str] = []
        enemies = list(row.get("enemy_heroes") or [])
        mid = int(row.get("match_id") or 0)
        for event in row.get("purchase_log") or []:
            name = normalize_item_name(event.get("key"))
            label = vocab.encode(name) if name else None
            if label is None:
                continue
            minute = max(0, int(event.get("time") or 0) // 60)
            gold = float(gold_t[minute]) if minute < len(gold_t) else float(ITEM_COSTS.get(name, 2000))
            net_worth = gold
            level = min(25.0, 1 + minute * 0.7)
            xs.append(
                feature_vector(hero_id, role, minute, gold, net_worth, level, owned, enemies, vocab)
            )
            ys.append(label)
            match_ids.append(mid)
            owned.append(name)
    if not xs:
        raise ValueError("Нет сэмплов для обучения item-модели")
    return np.stack(xs), np.array(ys, dtype=np.int64), np.array(match_ids, dtype=np.int64)


def split_by_match(
    x: np.ndarray,
    y: np.ndarray,
    match_ids: np.ndarray,
    val_ratio: float = 0.2,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = rng or np.random.default_rng(7)
    unique = np.unique(match_ids)
    rng.shuffle(unique)
    cut = max(1, int(len(unique) * val_ratio)) if len(unique) > 4 else 1
    val_matches = set(unique[:cut].tolist())
    train_mask = np.array([mid not in val_matches for mid in match_ids])
    val_mask = ~train_mask
    if not train_mask.any() or not val_mask.any():
        # fallback random split
        perm = rng.permutation(len(x))
        n_val = max(1, int(len(x) * val_ratio))
        val_idx, train_idx = perm[:n_val], perm[n_val:]
        return x[train_idx], y[train_idx], x[val_idx], y[val_idx]
    return x[train_mask], y[train_mask], x[val_mask], y[val_mask]


def topk_accuracy(probs: np.ndarray, y: np.ndarray, k: int = 3) -> float:
    if len(y) == 0:
        return 0.0
    top = np.argsort(probs, axis=1)[:, -k:]
    hits = sum(1 for i, label in enumerate(y) if label in top[i])
    return hits / len(y)


class ItemMLP:
    def __init__(self, in_dim: int, n_classes: int, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng(7)
        self.w1 = self.rng.normal(0, np.sqrt(2.0 / in_dim), (in_dim, HIDDEN1)).astype(np.float32)
        self.b1 = np.zeros(HIDDEN1, dtype=np.float32)
        self.w2 = self.rng.normal(0, np.sqrt(2.0 / HIDDEN1), (HIDDEN1, HIDDEN2)).astype(np.float32)
        self.b2 = np.zeros(HIDDEN2, dtype=np.float32)
        self.w3 = self.rng.normal(0, np.sqrt(2.0 / HIDDEN2), (HIDDEN2, n_classes)).astype(np.float32)
        self.b3 = np.zeros(n_classes, dtype=np.float32)

    def forward(self, x: np.ndarray, drop: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        h1 = np.maximum(0.0, x @ self.w1 + self.b1)
        if drop > 0:
            mask = (self.rng.random(h1.shape) > drop).astype(np.float32)
            h1 = h1 * mask / max(1e-6, 1.0 - drop)
        h2 = np.maximum(0.0, h1 @ self.w2 + self.b2)
        if drop > 0:
            mask = (self.rng.random(h2.shape) > drop).astype(np.float32)
            h2 = h2 * mask / max(1e-6, 1.0 - drop)
        logits = h2 @ self.w3 + self.b3
        return h1, h2, logits

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            x = x[None, :]
        _, _, logits = self.forward(x, drop=0.0)
        return _softmax(logits)

    def train(
        self,
        x: np.ndarray,
        y: np.ndarray,
        x_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        epochs: int = 60,
        lr: float = 0.008,
        batch_size: int = 64,
        drop: float = 0.1,
        patience: int = 10,
    ) -> dict[str, Any]:
        losses: list[float] = []
        best_val = -1.0
        best_weights: dict[str, np.ndarray] | None = None
        stale = 0
        n = len(x)
        for epoch in range(epochs):
            perm = self.rng.permutation(n)
            total = 0.0
            for start in range(0, n, batch_size):
                idx = perm[start : start + batch_size]
                batch_x = x[idx]
                batch_y = y[idx]
                h1, h2, logits = self.forward(batch_x, drop=drop)
                probs = _softmax(logits)
                onehot = np.zeros_like(probs)
                onehot[np.arange(len(batch_y)), batch_y] = 1.0
                loss = -np.mean(np.log(np.clip(probs[np.arange(len(batch_y)), batch_y], 1e-8, 1.0)))
                total += float(loss) * len(batch_y)
                dlogits = (probs - onehot) / len(batch_y)
                dw3 = h2.T @ dlogits
                db3 = dlogits.sum(axis=0)
                dh2 = (dlogits @ self.w3.T) * (h2 > 0)
                dw2 = h1.T @ dh2
                db2 = dh2.sum(axis=0)
                dh1 = (dh2 @ self.w2.T) * (h1 > 0)
                dw1 = batch_x.T @ dh1
                db1 = dh1.sum(axis=0)
                self.w3 -= lr * dw3
                self.b3 -= lr * db3
                self.w2 -= lr * dw2
                self.b2 -= lr * db2
                self.w1 -= lr * dw1
                self.b1 -= lr * db1
            losses.append(total / n)
            val_top1 = 0.0
            if x_val is not None and y_val is not None and len(y_val):
                val_probs = self.predict_proba(x_val)
                val_top1 = topk_accuracy(val_probs, y_val, k=1)
                if val_top1 > best_val + 1e-4:
                    best_val = val_top1
                    best_weights = {
                        "w1": self.w1.copy(),
                        "b1": self.b1.copy(),
                        "w2": self.w2.copy(),
                        "b2": self.b2.copy(),
                        "w3": self.w3.copy(),
                        "b3": self.b3.copy(),
                    }
                    stale = 0
                else:
                    stale += 1
                    if stale >= patience:
                        break
            _ = epoch
        if best_weights is not None:
            self.w1, self.b1 = best_weights["w1"], best_weights["b1"]
            self.w2, self.b2 = best_weights["w2"], best_weights["b2"]
            self.w3, self.b3 = best_weights["w3"], best_weights["b3"]
        return {"losses": losses, "best_val_top1": best_val, "epochs_run": len(losses)}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            w1=self.w1,
            b1=self.b1,
            w2=self.w2,
            b2=self.b2,
            w3=self.w3,
            b3=self.b3,
        )

    @classmethod
    def load(cls, path: Path) -> "ItemMLP":
        data = np.load(path)
        if "w3" not in data.files:
            raise ValueError(
                f"Старая модель без 2 скрытых слоёв: {path}. Переобучи: python scripts\\train_items.py"
            )
        model = cls(int(data["w1"].shape[0]), int(data["w3"].shape[1]))
        model.w1 = data["w1"]
        model.b1 = data["b1"]
        model.w2 = data["w2"]
        model.b2 = data["b2"]
        model.w3 = data["w3"]
        model.b3 = data["b3"]
        return model


def _inventory_used(state: GameState, owned: set[str]) -> int:
    slots = int(getattr(state, "inventory_slots", 0) or 0)
    if slots > 0:
        return slots
    counted = [name for name in owned if name and name != "aghanims_shard"]
    return min(len(counted), INVENTORY_SLOT_LIMIT)


def _should_recommend(name: str, state: GameState, owned: set[str]) -> bool:
    key = normalize_item_name(name)
    if not key or key in owned:
        return False
    if not is_finished_item(key) or not item_allowed_for_hero(state.hero_id, key):
        return False
    boots = owned_boots(owned)
    slots = _inventory_used(state, owned)
    if key in BOOT_ITEMS:
        if boots:
            return key == "travel_boots_2" and "travel_boots" in boots
        if slots >= 5:
            return False
        if state.minute >= BOOT_LATE_MINUTE and key not in {"travel_boots", "travel_boots_2"}:
            return False
    if slots >= INVENTORY_SLOT_LIMIT and item_takes_inventory_slot(key):
        return is_upgrade_of_owned(key, owned)
    return True


class ItemModel:
    def __init__(self, mlp: ItemMLP, vocab: ItemVocab) -> None:
        self.mlp = mlp
        self.vocab = vocab

    def recommend(self, state: GameState, role: int = DEFAULT_LANE_ROLE, top_k: int = 3) -> list[tuple[str, float]]:
        if state.hero_id not in DEFAULT_HERO_IDS:
            return []
        gold = float(state.earned_gold or state.net_worth or state.gold)
        x = feature_vector(
            state.hero_id,
            role,
            state.minute,
            gold,
            float(state.net_worth or gold),
            float(state.level or max(1, state.minute)),
            state.items,
            state.enemy_heroes,
            self.vocab,
        )
        probs = self.mlp.predict_proba(x)[0]
        owned = {normalize_item_name(item) for item in state.items}
        bag = float(state.gold)
        ranked: list[tuple[str, float]] = []
        for idx in np.argsort(probs)[::-1]:
            name = self.vocab.names[int(idx)]
            if not _should_recommend(name, state, owned):
                continue
            cost = ITEM_COSTS.get(name, 2500)
            if bag > 0 and bag < cost * ITEM_HINT_GOLD_RATIO * 0.55 and state.minute >= 6:
                continue
            ranked.append((name, float(probs[int(idx)])))
            if len(ranked) >= top_k:
                break
        return ranked


def train_item_model(rows: list[dict[str, Any]]) -> tuple[ItemModel, dict[str, Any]]:
    vocab = build_vocab(rows)
    x, y, match_ids = build_dataset(rows, vocab)
    x_train, y_train, x_val, y_val = split_by_match(x, y, match_ids)
    model = ItemMLP(x.shape[1], len(vocab.names))
    train_info = model.train(x_train, y_train, x_val, y_val)
    val_probs = model.predict_proba(x_val) if len(y_val) else np.zeros((0, len(vocab.names)))
    report = {
        "samples": int(len(y)),
        "train_samples": int(len(y_train)),
        "val_samples": int(len(y_val)),
        "classes": len(vocab.names),
        "val_top1": round(topk_accuracy(val_probs, y_val, 1), 4) if len(y_val) else None,
        "val_top3": round(topk_accuracy(val_probs, y_val, 3), 4) if len(y_val) else None,
        "epochs_run": train_info["epochs_run"],
        "best_val_top1": train_info["best_val_top1"],
        "heroes": sorted({int(r.get("hero_id") or 0) for r in rows}),
    }
    return ItemModel(model, vocab), report


def save_item_model(
    model: ItemModel,
    model_path: Path | None = None,
    vocab_path: Path | None = None,
    report: dict[str, Any] | None = None,
) -> None:
    model_path = model_path or ITEM_MODEL_PATH
    vocab_path = vocab_path or ITEM_VOCAB_PATH
    model.mlp.save(model_path)
    vocab_path.parent.mkdir(parents=True, exist_ok=True)
    vocab_path.write_text(json.dumps(model.vocab.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    if report is not None:
        report_path = PROCESSED_DIR / "item_train_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def load_item_model(model_path: Path | None = None, vocab_path: Path | None = None) -> ItemModel | None:
    model_path = model_path or ITEM_MODEL_PATH
    vocab_path = vocab_path or ITEM_VOCAB_PATH
    if not model_path.exists() or not vocab_path.exists():
        return None
    vocab = ItemVocab.from_json(json.loads(vocab_path.read_text(encoding="utf-8")))
    mlp = ItemMLP.load(model_path)
    return ItemModel(mlp, vocab)
