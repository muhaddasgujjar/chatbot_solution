param(
  [string]$ApiBaseUrl = "http://127.0.0.1:8000",
  [string]$UserId = "retrieval-eval-user",
  [string]$Role = "all",
  [string]$QueryFile = "",
  [int]$MaxQueries = 25
)

$ErrorActionPreference = "Stop"

function Normalize-UrlPath {
  param([string]$Url)
  if ([string]::IsNullOrWhiteSpace($Url)) { return "" }
  try {
    $uri = [System.Uri]$Url
    return ($uri.AbsolutePath.TrimEnd("/")).ToLower()
  } catch {
    return ""
  }
}

function Get-Queries {
  param(
    [string]$Path,
    [int]$Limit
  )

  if ($Path -and (Test-Path $Path)) {
    $raw = Get-Content -Path $Path -Raw
    $parsed = $raw | ConvertFrom-Json
    if ($parsed -is [System.Array]) {
      $normalized = @()
      foreach ($item in ($parsed | Select-Object -First $Limit)) {
        if ($item -is [string]) {
          $normalized += [PSCustomObject]@{
            query                    = $item
            expected_source_contains = ""
            reference_url            = ""
          }
        } else {
          $queryText = [string]$item.query
          if ([string]::IsNullOrWhiteSpace($queryText)) {
            throw "Each query object in QueryFile must include a non-empty 'query' field."
          }
          $normalized += [PSCustomObject]@{
            query                    = $queryText
            expected_source_contains = [string]$item.expected_source_contains
            reference_url            = [string]$item.reference_url
          }
        }
      }
      return $normalized
    }
    throw "QueryFile must contain a JSON array of query strings."
  }

  $defaults = @(
    [PSCustomObject]@{ query = "How do I reset my Oakland University password?"; expected_source_contains = "password"; reference_url = "" },
    [PSCustomObject]@{ query = "How can I contact OU IT support?"; expected_source_contains = "support"; reference_url = "" },
    [PSCustomObject]@{ query = "How do I connect to campus wifi?"; expected_source_contains = "wifi"; reference_url = "" },
    [PSCustomObject]@{ query = "How can I create a help desk ticket?"; expected_source_contains = "ticket"; reference_url = "" },
    [PSCustomObject]@{ query = "Where can I get help with student portal login?"; expected_source_contains = "portal"; reference_url = "" }
  )
  return @($defaults | Select-Object -First $Limit)
}

function Invoke-ChatAndGetEndEvent {
  param(
    [string]$BaseUrl,
    [string]$Query,
    [string]$EvalUserId,
    [string]$EvalRole
  )

  $body = @{
    query   = $Query
    user_id = $EvalUserId
    role    = $EvalRole
  } | ConvertTo-Json

  $response = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/api/chat" -Method POST -ContentType "application/json" -Body $body
  if ($response.StatusCode -ne 200) {
    throw "Chat request failed with status $($response.StatusCode) for query: $Query"
  }

  $events = $response.Content -split "`n`n"
  foreach ($event in $events) {
    $line = ($event -split "`n" | Where-Object { $_ -like "data:*" } | Select-Object -First 1)
    if (-not $line) { continue }
    $jsonLine = $line.Substring(5).Trim()
    if (-not $jsonLine) { continue }
    try {
      $payload = $jsonLine | ConvertFrom-Json
      if ($payload.type -eq "end") {
        return $payload
      }
    } catch {
      continue
    }
  }

  throw "Did not find SSE end event for query: $Query"
}

Write-Host "Retrieval evaluation starting against $ApiBaseUrl"
$health = Invoke-WebRequest -UseBasicParsing "$ApiBaseUrl/health"
if ($health.StatusCode -ne 200) {
  throw "Health check failed. Ensure backend is running."
}

$queries = Get-Queries -Path $QueryFile -Limit $MaxQueries
if ($queries.Count -eq 0) {
  throw "No queries provided for retrieval evaluation."
}

$results = @()
foreach ($query in $queries) {
  $endPayload = Invoke-ChatAndGetEndEvent -BaseUrl $ApiBaseUrl -Query $query.query -EvalUserId $UserId -EvalRole $Role
  $metrics = $endPayload.quality_metrics
  $topSource = if ($endPayload.sources -and $endPayload.sources.Count -gt 0) { [string]$endPayload.sources[0] } else { "" }
  $topSources = @()
  if ($endPayload.sources) {
    $topSources = @($endPayload.sources | Select-Object -First 3 | ForEach-Object { [string]$_ })
  }
  $expectedHint = [string]$query.expected_source_contains
  $referenceUrl = [string]$query.reference_url
  $isLabeled = (-not [string]::IsNullOrWhiteSpace($referenceUrl)) -or (-not [string]::IsNullOrWhiteSpace($expectedHint))
  $matchTop1 = $false
  $matchTop3 = $false
  $matchMode = ""
  if ($isLabeled -and $topSources.Count -gt 0) {
    $topPath = Normalize-UrlPath $topSource
    $top3Paths = @($topSources | ForEach-Object { Normalize-UrlPath $_ })
    $refPath = Normalize-UrlPath $referenceUrl
    if (-not [string]::IsNullOrWhiteSpace($refPath)) {
      $matchTop1 = $topPath -eq $refPath
      $matchTop3 = $top3Paths -contains $refPath
      $matchMode = "reference_url_path"
    } elseif (-not [string]::IsNullOrWhiteSpace($expectedHint)) {
      $hintLower = $expectedHint.ToLower()
      $matchTop1 = $topSource.ToLower().Contains($hintLower)
      $matchTop3 = @($topSources | Where-Object { $_.ToLower().Contains($hintLower) }).Count -gt 0
      $matchMode = "expected_source_contains"
    }
  }
  $record = [PSCustomObject]@{
    query            = $query.query
    confidence       = [double]$endPayload.confidence
    requires_handoff = [bool]$endPayload.requires_handoff
    source_count     = [int]($metrics.source_count)
    chunk_count      = [int]($metrics.chunk_count)
    top_score        = [double]($metrics.top_score)
    avg_score        = [double]($metrics.avg_score)
    score_spread     = [double]($metrics.score_spread)
    low_confidence   = [bool]($metrics.low_confidence)
    expected_hint    = $expectedHint
    reference_url    = $referenceUrl
    match_mode       = $matchMode
    top_source       = $topSource
    source_hit_top1  = if ($isLabeled) { $matchTop1 } else { $null }
    source_hit_top3  = if ($isLabeled) { $matchTop3 } else { $null }
  }
  $results += $record
}

$handoffCount = ($results | Where-Object { $_.requires_handoff }).Count
$avgConfidence = [Math]::Round((($results | Measure-Object -Property confidence -Average).Average), 4)
$avgTopScore = [Math]::Round((($results | Measure-Object -Property top_score -Average).Average), 4)
$avgSourceCount = [Math]::Round((($results | Measure-Object -Property source_count -Average).Average), 2)
$lowConfidenceCount = ($results | Where-Object { $_.low_confidence }).Count
$labeled = @($results | Where-Object { (-not [string]::IsNullOrWhiteSpace($_.expected_hint)) -or (-not [string]::IsNullOrWhiteSpace($_.reference_url)) })
$labeledCount = $labeled.Count
$hitTop1Count = @($labeled | Where-Object { $_.source_hit_top1 -eq $true }).Count
$hitTop3Count = @($labeled | Where-Object { $_.source_hit_top3 -eq $true }).Count
$top1HitRate = if ($labeledCount -gt 0) { [Math]::Round(($hitTop1Count / $labeledCount), 4) } else { 0.0 }
$top3HitRate = if ($labeledCount -gt 0) { [Math]::Round(($hitTop3Count / $labeledCount), 4) } else { 0.0 }

Write-Host ""
Write-Host "=== Retrieval Evaluation Summary ==="
Write-Host "Queries evaluated: $($results.Count)"
Write-Host "Avg confidence: $avgConfidence"
Write-Host "Avg top score: $avgTopScore"
Write-Host "Avg source count: $avgSourceCount"
Write-Host "Requires handoff count: $handoffCount"
Write-Host "Low-confidence count: $lowConfidenceCount"
Write-Host "Labeled queries: $labeledCount"
Write-Host "Top-1 source hit count: $hitTop1Count"
Write-Host "Top-1 source hit rate: $top1HitRate"
Write-Host "Top-3 source hit count: $hitTop3Count"
Write-Host "Top-3 source hit rate: $top3HitRate"
Write-Host ""
Write-Host "=== Per-query metrics ==="
$results | Format-Table query, confidence, top_score, avg_score, source_count, requires_handoff, match_mode, source_hit_top1, source_hit_top3, top_source -AutoSize
