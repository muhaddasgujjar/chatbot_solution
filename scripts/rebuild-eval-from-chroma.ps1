param(
  [int]$MaxQueries = 50,
  [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutFile)) {
  $OutFile = Join-Path $repoRoot "scripts\eval-queries.generated.json"
}

$py = @'
import json
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, r"D:/projects/chatbot_solution/backend")
from app.core.retrieval import _collection

limit = int(sys.argv[1])
out_path = sys.argv[2]

# Chroma get returns up to limit rows; increase if needed for unique URL diversity
data = _collection.get(include=["metadatas"], limit=50000)
metas = data.get("metadatas") or []
urls = []
for m in metas:
    if not m:
        continue
    u = (m.get("source_url") or "").strip()
    if u and u.startswith("http"):
        urls.append(u)

# Dedupe preserving order
seen = set()
unique = []
for u in urls:
    if u not in seen:
        seen.add(u)
        unique.append(u)

rows = []
for url in unique[:limit]:
    path = urlparse(url).path or "/"
    slug = path.strip("/").split("/")[-1] or "page"
    slug = re.sub(r"\.[a-z]+$", "", slug, flags=re.I)
    tokens = [t for t in re.split(r"[-_]+", slug) if len(t) >= 3]
    hint = (tokens[0] if tokens else slug).lower()[:40]
    q = f"What does OU offer at {path.split('/')[-1] or 'this page'}?"
    if len(q) > 180:
        q = q[:177] + "..."
    rows.append({
        "query": q,
        "expected_source_contains": hint,
        "reference_url": url,
    })

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2)

print(f"Wrote {len(rows)} labeled rows from {len(unique)} unique URLs to {out_path}")
'@

$tmp = Join-Path $env:TEMP "rebuild-eval-chroma.py"
$outAbs = (Resolve-Path -Path (Split-Path -Parent $OutFile) -ErrorAction SilentlyContinue)
if (-not $outAbs) { New-Item -ItemType Directory -Path (Split-Path -Parent $OutFile) -Force | Out-Null }
$outFull = [System.IO.Path]::GetFullPath($OutFile)

Set-Content -Path $tmp -Value $py -Encoding UTF8
$backendDir = Join-Path $repoRoot "backend"
Push-Location $backendDir
try {
  & "D:/projects/chatbot_solution/backend/.venv/Scripts/python.exe" $tmp $MaxQueries $outFull
} finally {
  Pop-Location
  Remove-Item $tmp -ErrorAction SilentlyContinue
}
