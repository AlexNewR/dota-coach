from __future__ import annotations

import json
from pathlib import Path

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
headers = {
    "User-Agent": UA,
    "Accept": "application/json,text/html,*/*",
    "Referer": "https://dota2protracker.com/hero/Io?role=Mid",
}
candidates = [
    "https://dota2protracker.com/hero/Io/__data.json?role=Mid",
    "https://dota2protracker.com/hero/Io/__data.json",
    "https://dota2protracker.com/hero/Io.json?role=Mid",
    "https://dota2protracker.com/api/hero/Io",
    "https://dota2protracker.com/api/hero/91",
    "https://dota2protracker.com/api/heroes/Io",
    "https://dota2protracker.com/api/v1/hero/Io",
    "https://api.dota2protracker.com/hero/Io",
    "https://dota2protracker.com/hero/Io?role=Mid&x-sveltekit-invalidated=1",
]
out = Path(r"C:\Users\alwexn\Desktop\dota train\data\raw\api_probe.txt")
lines = []
with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
    for url in candidates:
        try:
            r = client.get(url)
            ct = r.headers.get("content-type", "")
            snippet = r.text[:180].replace("\n", " ")
            line = f"{r.status_code} {len(r.content):6d} {ct:40s} {url}\n  {snippet}"
        except Exception as exc:
            line = f"ERR {url} {exc}"
        print(line)
        lines.append(line)
out.write_text("\n".join(lines), encoding="utf-8")
