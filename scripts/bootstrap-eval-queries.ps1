param(
  [string]$SeedUrl = "https://support.oakland.edu",
  [int]$MaxPages = 25,
  [string]$OutFile = ".\scripts\eval-queries.generated.json"
)

$ErrorActionPreference = "Stop"

$pythonScript = @'
import json
import re
import sys
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

seed_url = sys.argv[1]
max_pages = int(sys.argv[2])
out_file = sys.argv[3]

seed_host = urlparse(seed_url).hostname or ""

def tokenize_slug(path: str):
    parts = [p for p in path.split("/") if p]
    if not parts:
        return []
    leaf = parts[-1]
    tokens = [t.lower() for t in re.split(r"[-_]+", leaf) if len(t) >= 4]
    return tokens

queue = deque([seed_url])
seen = set()
pages = []

while queue and len(pages) < max_pages:
    url = queue.popleft().split("#")[0]
    if url in seen:
        continue
    seen.add(url)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        continue
    if (parsed.hostname or "") != seed_host:
        continue
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except Exception:
        continue
    soup = BeautifulSoup(resp.text, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = " ".join(h1.get_text(" ", strip=True).split())
    pages.append((url, title))

    for a in soup.find_all("a", href=True):
        nxt = urljoin(url, a["href"]).split("#")[0]
        if nxt not in seen:
            queue.append(nxt)

generated = []
for url, title in pages:
    parsed = urlparse(url)
    tokens = tokenize_slug(parsed.path)
    expected_hint = tokens[0] if tokens else (parsed.path.strip("/").lower()[:20] if parsed.path.strip("/") else "support")
    query = f"How do I {title.lower()}?" if title else f"How do I use {expected_hint}?"
    generated.append(
        {
            "query": query[:180],
            "expected_source_contains": expected_hint,
            "reference_url": url,
        }
    )

with open(out_file, "w", encoding="utf-8") as f:
    json.dump(generated, f, indent=2)

print(f"Generated {len(generated)} labeled query seeds into {out_file}")
'@

$tmpPy = Join-Path $env:TEMP "bootstrap-eval-queries.py"
Set-Content -Path $tmpPy -Value $pythonScript -Encoding UTF8
try {
  .\backend\.venv\Scripts\python $tmpPy $SeedUrl $MaxPages $OutFile
} finally {
  Remove-Item -Path $tmpPy -ErrorAction SilentlyContinue
}
