from __future__ import annotations

import re
from pathlib import Path

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
base = "https://dota2protracker.com"
headers = {"User-Agent": UA}
html = httpx.get(base + "/hero/Io?role=Mid", headers=headers, timeout=30).text
assets = re.findall(r'/_app/immutable/[^"\']+\.js', html)
print("assets in html", len(assets))
# also start/app already known
extra = [
    "/_app/immutable/entry/start.MMWq_d4J.js",
    "/_app/immutable/entry/app.C5Wsl4W9.js",
]
urls = sorted(set(assets + extra))
out_dir = Path(r"C:\Users\alwexn\Desktop\dota train\data\raw\d2pt_js")
out_dir.mkdir(parents=True, exist_ok=True)
all_hits: set[str] = set()
with httpx.Client(timeout=30, headers=headers) as client:
    for path in urls:
        url = base + path
        try:
            text = client.get(url).text
        except Exception as exc:
            print("fail", path, exc)
            continue
        (out_dir / Path(path).name).write_text(text, encoding="utf-8", errors="replace")
        hits = set(re.findall(r'["\'](/api/[^"\']+)["\']', text))
        hits |= set(re.findall(r'["\'](https://[^"\']+/api/[^"\']+)["\']', text))
        hits |= set(re.findall(r'`(/api/[^`]+)`', text))
        if hits:
            print(Path(path).name, sorted(hits)[:30])
            all_hits |= hits
print("ALL API", sorted(all_hits))
# also scan for fetch(" 
fetch_hits = []
for js in out_dir.glob("*.js"):
    text = js.read_text(encoding="utf-8", errors="replace")
    for m in re.findall(r'fetch\(([^)]{0,180})\)', text)[:8]:
        fetch_hits.append((js.name, m[:180]))
print("fetch samples", len(fetch_hits))
for name, m in fetch_hits[:25]:
    print(name, m)
