from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
url = "https://dota2protracker.com/hero/Io?role=Mid"
with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
    response = client.get(url)
print("status", response.status_code, "len", len(response.text), "ct", response.headers.get("content-type"))
html = response.text
(OUT / "probe_io.html").write_text(html, encoding="utf-8", errors="replace")

srcs = re.findall(r'src="([^"]+)"', html)
print("srcs", len(srcs))
for src in srcs[:50]:
    print(" SRC", src)

api_like = sorted(
    set(
        re.findall(
            r'["\'](/[^"\']*(?:api|json|graphql|hero|match|build)[^"\']*)["\']',
            html,
            re.I,
        )
    )
)
print("api-like", len(api_like))
for item in api_like[:80]:
    print(" API", item)

abs_api = sorted(set(re.findall(r'https?://[^"\'\s]+(?:api|json)[^"\'\s]*', html, re.I)))
print("abs", abs_api[:40])

for js_url in srcs:
    if not js_url.endswith((".js", ".mjs")):
        continue
    if js_url.startswith("/"):
        js_url = "https://dota2protracker.com" + js_url
    elif js_url.startswith("./"):
        js_url = "https://dota2protracker.com/" + js_url[2:]
    elif not js_url.startswith("http"):
        continue
    try:
        js = httpx.get(js_url, headers={"User-Agent": UA}, timeout=30).text
    except Exception as exc:
        print("js fail", js_url, exc)
        continue
    hits = sorted(
        set(
            re.findall(
                r'["\'](/[^"\']{3,120}(?:api|json|graphql|hero|matches|builds)[^"\']*)["\']',
                js,
                re.I,
            )
        )
    )
    http_hits = sorted(set(re.findall(r'https?://[^"\'\s]{8,160}', js)))
    if hits or any("dota2protracker" in h or "api" in h.lower() for h in http_hits):
        print("JS", js_url, "hits", len(hits), "http", len(http_hits))
        for hit in hits[:40]:
            print("  H", hit)
        for hit in http_hits:
            if any(k in hit.lower() for k in ("dota2protracker", "api.", "/api", "stratz", "opendota")):
                print("  U", hit[:180])
