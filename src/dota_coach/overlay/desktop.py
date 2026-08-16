from __future__ import annotations

import argparse
import ctypes
import os
import socket
import sys
import threading
import time
import tkinter as tk
from typing import Any

BG = "#101218"
PANEL = "#171b24"
TEXT = "#ece7d8"
MUTED = "#9aa3b2"
GOLD = "#d4b15f"
OK = "#6fbf8a"
BAD = "#c45c4a"
HINT_BG = "#1d2330"
FONT = "Segoe UI"
MIN_W = 300
MIN_H = 240
VK_F8 = 0x77

user32 = ctypes.windll.user32


def _fmt_clock(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _pace(value: int, p50: Any) -> str:
    if not p50:
        return MUTED
    return OK if value >= p50 else BAD


class CoachDesktop:
    def __init__(self, width: int, height: int, x: int, y: int) -> None:
        self.root = tk.Tk()
        self.root.title("Dota Coach")
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(MIN_W, MIN_H)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.visible = True
        self._f8_held = False
        self._hint_visible = False
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.root.after(200, self._tick)
        self.root.after(40, self._poll_hotkey)
        self.root.bind("<F8>", lambda _e: None)
        self.root.focus_force()

    def _label(self, parent: tk.Misc, **kwargs) -> tk.Label:
        kwargs.setdefault("bg", parent.cget("bg") if hasattr(parent, "cget") else BG)
        kwargs.setdefault("fg", TEXT)
        kwargs.setdefault("font", (FONT, 10))
        kwargs.setdefault("anchor", "w")
        kwargs.setdefault("justify", "left")
        return tk.Label(parent, **kwargs)

    def _build(self) -> None:
        pad = {"padx": 12, "pady": 2}
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=12, pady=(12, 4))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        self.eyebrow = self._label(left, text="DOTA2PROTRACKER · МИД", fg=GOLD, font=(FONT, 8, "bold"))
        self.eyebrow.pack(anchor="w")
        self.hero = self._label(left, text="Ожидание матча", font=(FONT, 14, "bold"))
        self.hero.pack(anchor="w")
        self.detected = self._label(left, text="", fg=MUTED, font=(FONT, 9))
        self.detected.pack(anchor="w")
        self.clock = self._label(header, text="0:00", fg=GOLD, font=(FONT, 16), anchor="e")
        self.clock.pack(side="right", padx=(8, 0))

        stats = tk.Frame(self.root, bg=BG)
        stats.pack(fill="x", padx=10, pady=8)
        self.stat_values: dict[str, tk.Label] = {}
        for col, (key, title) in enumerate(
            (("kda", "K/D/A"), ("lh", "LH"), ("gpm", "GPM"), ("gold", "Всего"))
        ):
            cell = tk.Frame(stats, bg=PANEL, highlightthickness=0)
            cell.grid(row=0, column=col, sticky="nsew", padx=3, ipady=6)
            stats.grid_columnconfigure(col, weight=1)
            self._label(cell, text=title, fg=MUTED, font=(FONT, 8), bg=PANEL, anchor="center").pack()
            value = self._label(cell, text="0", font=(FONT, 13, "bold"), bg=PANEL, anchor="center")
            value.pack()
            self.stat_values[key] = value

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12)
        self.farm = self._label(body, text="", fg=MUTED, font=(FONT, 9), wraplength=340)
        self.farm.pack(fill="x", **pad)
        self.matchup = self._label(body, text="", fg=MUTED, font=(FONT, 9), wraplength=340)
        self.matchup.pack(fill="x", **pad)
        self.items = self._label(body, text="", fg=MUTED, font=(FONT, 9), wraplength=340)
        self.items.pack(fill="x", **pad)
        self.items_bad = self._label(body, text="", fg=BAD, font=(FONT, 9, "bold"), wraplength=340)
        self.items_bad.pack(fill="x", **pad)
        self.recs = self._label(body, text="", fg=MUTED, font=(FONT, 9), wraplength=340)
        self.recs.pack(fill="x", **pad)
        self.counters = self._label(body, text="", fg=OK, font=(FONT, 9), wraplength=340)
        self.counters.pack(fill="x", **pad)

        self.hint = tk.Frame(body, bg=HINT_BG, highlightbackground=GOLD, highlightthickness=2)
        self.hint_title = self._label(self.hint, text="", bg=HINT_BG, font=(FONT, 11, "bold"))
        self.hint_title.pack(anchor="w", padx=10, pady=(8, 2))
        self.hint_body = self._label(self.hint, text="", bg=HINT_BG, font=(FONT, 9), wraplength=320)
        self.hint_body.pack(anchor="w", padx=10)
        self.hint_instead = self._label(self.hint, text="", bg=HINT_BG, fg=OK, font=(FONT, 9, "bold"), wraplength=320)
        self.hint_instead.pack(anchor="w", padx=10, pady=(4, 8))

        foot = self._label(self.root, text="F8 — скрыть / показать", fg=MUTED, font=(FONT, 8), anchor="center")
        foot.pack(fill="x", pady=(4, 8))
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        wrap = max(200, event.width - 40)
        for widget in (self.farm, self.matchup, self.items, self.items_bad, self.recs, self.counters, self.hint_body, self.hint_instead):
            widget.configure(wraplength=wrap)

    def _poll_hotkey(self) -> None:
        # Dota перехватывает RegisterHotKey; GetAsyncKeyState видит F8 даже без фокуса.
        down = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
        if down and not self._f8_held:
            self.toggle()
        self._f8_held = down
        self.root.after(40, self._poll_hotkey)

    def toggle(self) -> None:
        if self.visible:
            self.root.withdraw()
            self.visible = False
        else:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.visible = True

    def _tick(self) -> None:
        try:
            from dota_coach.gsi.server import get_snapshot

            self.render(get_snapshot())
        except Exception:
            pass
        self.root.after(250, self._tick)

    def render(self, data: dict[str, Any]) -> None:
        hero = data.get("hero") or ""
        if hero:
            self.hero.configure(text=hero)
            extra = f"id {data.get('hero_id')}" if data.get("hero_id") else ""
            loading = " · качаю билд D2PT" if data.get("book_status") == "loading" else ""
            self.detected.configure(text=f"Определён: {hero}" + (f" · {extra}" if extra else "") + loading)
        elif data.get("connected"):
            self.hero.configure(text="Герой ещё не пришёл" if data.get("in_game") else "Ожидание матча")
            self.detected.configure(text="")
        else:
            self.hero.configure(text="Нет GSI")
            self.detected.configure(text="")
        self.clock.configure(text=_fmt_clock(int(data.get("clock") or 0)))

        kda = data.get("kda") or [0, 0, 0]
        self.stat_values["kda"].configure(text="/".join(str(part) for part in kda), fg=TEXT)
        self.stat_values["lh"].configure(text=str(data.get("last_hits") or 0))
        self.stat_values["gpm"].configure(text=str(data.get("gpm") or 0))
        self.stat_values["gold"].configure(text=str(data.get("gold") or 0))

        farm = data.get("farm") or {}
        gpm_fg = _pace(int(data.get("gpm") or farm.get("gpm") or 0), farm.get("gpm_p50"))
        gold_fg = _pace(int(data.get("gold") or farm.get("gold") or 0), farm.get("gold_p50"))
        lh_fg = _pace(int(data.get("last_hits") or 0), farm.get("lh_p50"))
        self.stat_values["gpm"].configure(fg=gpm_fg)
        self.stat_values["gold"].configure(fg=gold_fg)
        self.stat_values["lh"].configure(fg=lh_fg)

        if farm:
            self.farm.configure(
                text=(
                    f"Фарм @{farm.get('minute', 0)}м: {farm.get('lh', 0)} LH · "
                    f"про p25/p50 = {round(farm.get('lh_p25') or 0)}/{round(farm.get('lh_p50') or 0)}"
                )
            )
        else:
            self.farm.configure(text="Фарм: нет бенчмарка")

        enemies = ", ".join(str(row.get("name") or "") for row in (data.get("enemies") or []) if row.get("name"))
        self.matchup.configure(text=f"Против: {enemies}" if enemies else "Против: —")

        items = data.get("items") or []
        ok = [row.get("label") or row.get("name") for row in items if isinstance(row, dict) and not row.get("bad")]
        bad = [row.get("label") or row.get("name") for row in items if isinstance(row, dict) and row.get("bad")]
        if items and not isinstance(items[0], dict):
            ok = [str(name) for name in items]
            bad = []
        self.items.configure(text="Предметы: " + (", ".join(str(name) for name in ok if name) or "—"))
        self.items_bad.configure(text=("Плохой выбор: " + ", ".join(str(name) for name in bad if name)) if bad else "")

        recs_list = data.get("recommended") or []
        if recs_list:
            bits = []
            for row in recs_list:
                label = row.get("label") or ""
                if not label:
                    continue
                if row.get("p") is not None:
                    bits.append(f"{label} ({row['p']:.0%})")
                else:
                    bits.append(str(label))
            prefix = "Следующий предмет"
            self.recs.configure(text=f"{prefix}: " + ", ".join(bits))
        else:
            self.recs.configure(text="Рекомендация: —")

        counters = data.get("counters") or []
        if counters:
            bits = [f"{row.get('label')} ({row.get('enemy')})" for row in counters if row.get("label")]
            self.counters.configure(text="Контр: " + ", ".join(bits), fg=OK)
        else:
            self.counters.configure(text="Контр: —", fg=MUTED)

        hint = data.get("hint")
        if hint and (hint.get("title") or hint.get("body")):
            color = {"bad": BAD, "warn": GOLD}.get(str(hint.get("severity") or ""), GOLD)
            self.hint.configure(highlightbackground=color)
            self.hint_title.configure(text=hint.get("title") or "")
            self.hint_body.configure(text=hint.get("body") or "")
            instead = hint.get("instead") or ""
            self.hint_instead.configure(text=f"Верный выбор: {instead}" if instead else "")
            if not self._hint_visible:
                self.hint.pack(fill="x", pady=8)
                self._hint_visible = True
        elif self._hint_visible:
            self.hint.pack_forget()
            self._hint_visible = False

    def run(self) -> None:
        self.root.mainloop()


def _find_free_port(host: str, start: int, end: int = 3100) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Не нашёл свободный порт на {host} в диапазоне {start}-{end}")


def _wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Dota Coach — десктоп-оверлей")
    parser.add_argument("--x", type=int, default=16)
    parser.add_argument("--y", type=int, default=80)
    parser.add_argument("--width", type=int, default=380)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-update", action="store_true", help="Не проверять GitHub Releases")
    args = parser.parse_args()

    if not args.no_update:
        from dota_coach.update import maybe_update

        if maybe_update():
            sys.exit(0)

    base_host = os.getenv("DOTA_COACH_HOST", "127.0.0.1")
    base_port = int(args.port or os.getenv("DOTA_COACH_PORT", "3000"))
    port = _find_free_port(base_host, base_port)
    if port != base_port:
        print(f"Порт {base_port} занят, использую {port}")
    os.environ["DOTA_COACH_PORT"] = str(port)

    from dota_coach.gsi.install_cfg import main as install_main
    from dota_coach.gsi.server import app, get_engine
    import uvicorn

    try:
        install_main()
    except FileNotFoundError as exc:
        print(exc)
        print("Коуч всё равно запустится — положи конфиг в cfg/gamestate_integration вручную.")

    get_engine()
    host = os.getenv("DOTA_COACH_HOST", "127.0.0.1")
    gsi_port = int(os.getenv("DOTA_COACH_PORT", "3000"))
    threading.Thread(
        target=lambda: uvicorn.run(app, host=host, port=gsi_port, log_level="warning"),
        daemon=True,
    ).start()
    if not _wait_for_server(host, gsi_port):
        print(f"GSI-сервер не поднялся ({host}:{gsi_port})")
        sys.exit(1)

    print(f"GSI слушает {host}:{gsi_port}/gsi — браузер не нужен.")
    print("Dota 2: Borderless Windowed + -gamestateintegration")
    print("F8 — скрыть / показать окно (работает поверх Dota)")
    CoachDesktop(args.width, args.height, args.x, args.y).run()


if __name__ == "__main__":
    main()
