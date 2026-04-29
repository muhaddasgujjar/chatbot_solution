param(
  [string]$QueryFile = ".\scripts\eval-queries.example.json",
  [string]$Role = "all",
  [int]$TopK = 3
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not [System.IO.Path]::IsPathRooted($QueryFile)) {
  $rel = ($QueryFile -replace '^\.\\', '').TrimStart('/','\')
  $QueryFile = Join-Path $repoRoot $rel
}
if (-not (Test-Path $QueryFile)) {
  throw "Query file not found: $QueryFile"
}
$QueryFile = [System.IO.Path]::GetFullPath($QueryFile)

$pythonScript = @'
import json
import sys
from itertools import product

sys.path.insert(0, r"D:/projects/chatbot_solution/backend")

from app.core.config import settings
from app.core.retrieval import retrieve_context

query_file = sys.argv[1]
role = sys.argv[2]
top_k = int(sys.argv[3])

with open(query_file, "r", encoding="utf-8") as f:
    queries = json.load(f)

normalized = []
for item in queries:
    if isinstance(item, str):
        normalized.append({"query": item, "expected_source_contains": "", "reference_url": ""})
    elif isinstance(item, dict):
        q = str(item.get("query", "")).strip()
        if not q:
            continue
        normalized.append(
            {
                "query": q,
                "expected_source_contains": str(item.get("expected_source_contains", "")).strip().lower(),
                "reference_url": str(item.get("reference_url", "")).strip(),
            }
        )

labeled = [q for q in normalized if q["expected_source_contains"] or q["reference_url"]]
if not labeled:
    raise SystemExit("No labeled queries found. Provide reference_url and/or expected_source_contains values.")

semantic_grid = [0.5, 0.6, 0.7]
keyword_grid = [0.2, 0.3, 0.4]
url_grid = [0.05, 0.1, 0.2]
short_penalty_grid = [0.05, 0.08, 0.1]
long_penalty_grid = [0.03, 0.05, 0.08]

def evaluate_config(sem, keyw, urlw, shortp, longp):
    settings.rerank_semantic_weight = sem
    settings.rerank_keyword_weight = keyw
    settings.rerank_source_url_weight = urlw
    settings.rerank_short_chunk_penalty = shortp
    settings.rerank_long_chunk_penalty = longp

    hits_top1 = 0
    hits_top3 = 0
    for row in labeled:
        chunks = retrieve_context(row["query"], role, top_k)
        top_sources = [c.source_url.lower() for c in chunks[:3]]
        top_source = top_sources[0] if top_sources else ""
        matched_top1 = False
        matched_top3 = False
        reference_url = row["reference_url"].lower()
        if reference_url:
            try:
                from urllib.parse import urlparse
                ref_path = urlparse(reference_url).path.rstrip("/")
                matched_top1 = bool(top_source) and (urlparse(top_source).path.rstrip("/") == ref_path)
                matched_top3 = any(urlparse(s).path.rstrip("/") == ref_path for s in top_sources)
            except Exception:
                matched_top1 = False
                matched_top3 = False
        if (not matched_top1 or not matched_top3) and row["expected_source_contains"]:
            hint = row["expected_source_contains"]
            if not matched_top1 and top_source:
                matched_top1 = hint in top_source
            if not matched_top3:
                matched_top3 = any(hint in s for s in top_sources)
        if matched_top1:
            hits_top1 += 1
        if matched_top3:
            hits_top3 += 1
    hit_rate_top1 = hits_top1 / len(labeled)
    hit_rate_top3 = hits_top3 / len(labeled)
    return {
        "semantic": sem,
        "keyword": keyw,
        "url": urlw,
        "short_penalty": shortp,
        "long_penalty": longp,
        "hits_top1": hits_top1,
        "hits_top3": hits_top3,
        "total": len(labeled),
        "hit_rate_top1": hit_rate_top1,
        "hit_rate_top3": hit_rate_top3,
    }

results = []
for sem, keyw, urlw, shortp, longp in product(
    semantic_grid, keyword_grid, url_grid, short_penalty_grid, long_penalty_grid
):
    results.append(evaluate_config(sem, keyw, urlw, shortp, longp))

results.sort(key=lambda r: (r["hit_rate_top3"], r["hit_rate_top1"], r["hits_top3"], r["hits_top1"]), reverse=True)
best = results[0]

print("=== Rerank Sweep Summary ===")
print(f"Configs evaluated: {len(results)}")
print(f"Labeled queries: {best['total']}")
print("")
print("Best config:")
print(
    f"semantic={best['semantic']} keyword={best['keyword']} url={best['url']} "
    f"short_penalty={best['short_penalty']} long_penalty={best['long_penalty']}"
)
print(f"Top-1 hit rate: {best['hit_rate_top1']:.4f} ({best['hits_top1']}/{best['total']})")
print(f"Top-3 hit rate: {best['hit_rate_top3']:.4f} ({best['hits_top3']}/{best['total']})")
print("")
print("Top 5 configs:")
for row in results[:5]:
    print(
        f"hit_top1={row['hit_rate_top1']:.4f} ({row['hits_top1']}/{row['total']}) | "
        f"hit_top3={row['hit_rate_top3']:.4f} ({row['hits_top3']}/{row['total']}) | "
        f"semantic={row['semantic']} keyword={row['keyword']} url={row['url']} "
        f"short_penalty={row['short_penalty']} long_penalty={row['long_penalty']}"
    )
'@

Write-Host "Running rerank weight sweep..."
$tempPy = Join-Path $env:TEMP "sweep-rerank-temp.py"
Set-Content -Path $tempPy -Value $pythonScript -Encoding UTF8
$backendDir = Join-Path $repoRoot "backend"
Push-Location $backendDir
try {
  & "D:/projects/chatbot_solution/backend/.venv/Scripts/python.exe" $tempPy $QueryFile $Role $TopK
} finally {
  Pop-Location
  Remove-Item -Path $tempPy -ErrorAction SilentlyContinue
}
