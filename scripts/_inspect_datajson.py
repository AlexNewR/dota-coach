from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

url = "https://dota2protracker.com/hero/Io/__data.json?role=Mid"
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://dota2protracker.com/hero/Io?role=Mid",
}
text = httpx.get(url, headers=headers, timeout=30).text
Path(r"C:\Users\alwexn\Desktop\dota train\data\raw\io_data.json").write_text(text, encoding="utf-8")
print("len", len(text))
for key in ("avg_gpm", "item_stats", "avg_last_hits", "avg_deaths", "networth_10", "purchase_rate", "heroBuilds"):
    print(key, text.find(key))
data = json.loads(text)
# walk for dicts that look like item stats
found = []

def walk(obj, path=""):
    if len(found) > 30:
        return
    if isinstance(obj, dict):
        keys = set(obj)
        if {"pr", "wins", "win_rate", "purchases"} <= keys or {"purchase_rate", "avg_minute"} <= keys:
            found.append((path, {k: obj[k] for k in list(obj)[:8]}))
        if "avg_gpm" in obj or "gpm" in obj and "xpm" in obj:
            found.append((path + "/stats", {k: obj[k] for k in list(obj)[:20]}))
        for k, v in obj.items():
            walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list) and len(obj) < 5000:
        for i, v in enumerate(obj[:200]):
            walk(v, f"{path}[{i}]")

walk(data)
print("found", len(found))
for path, sample in found[:12]:
    print(path, sample)
