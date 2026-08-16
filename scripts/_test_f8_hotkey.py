"""Быстрая проверка F8: edge-trigger + LL-хук / GetAsyncKeyState."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import ctypes

from dota_coach.overlay.desktop import F8HotkeyWatcher, VK_F8, user32

KEYEVENTF_KEYUP = 0x0002


def _tap_f8() -> None:
    user32.keybd_event(VK_F8, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_F8, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)


def main() -> int:
    hits: list[float] = []
    watcher = F8HotkeyWatcher(lambda: hits.append(time.time()))
    watcher.start()
    time.sleep(0.15)
    print(f"hook_ok={watcher.hook_ok}")

    # Три нажатия → ровно 3 срабатывания (не на удержании).
    for _ in range(3):
        _tap_f8()
        time.sleep(0.1)

    # Удержание не должно давать лишних toggle.
    user32.keybd_event(VK_F8, 0, 0, 0)
    time.sleep(0.35)
    user32.keybd_event(VK_F8, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)

    if not watcher.hook_ok:
        print("LL-хук не встал — проверяю GetAsyncKeyState fallback")
        for _ in range(2):
            # Симулируем опрос как в overlay
            for _step in range(20):
                watcher.poll_async_fallback()
                time.sleep(0.02)
            _tap_f8()
            for _step in range(20):
                watcher.poll_async_fallback()
                time.sleep(0.02)

    watcher.stop()
    print(f"toggles={len(hits)} (ожидаем 4 при рабочем хуке: 3 тапа + 1 hold)")
    ok = len(hits) == 4 if watcher.hook_ok is False or True else False
    # После stop hook_ok=False; считаем по числу
    ok = len(hits) == 4
    if not ok:
        print("FAIL")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
