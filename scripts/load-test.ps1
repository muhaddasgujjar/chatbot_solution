param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [int]$Requests = 200,
  [int]$Concurrent = 10
)

$ErrorActionPreference = "Continue"

$BaseUrl = $BaseUrl.TrimEnd("/")
$perWorker = [math]::Max(1, [math]::Ceiling($Requests / $Concurrent))
$actualTotal = $perWorker * $Concurrent

Write-Host "Load test: ~$actualTotal GET $BaseUrl/health (concurrent workers: $Concurrent, per worker: $perWorker)"

$sw = [System.Diagnostics.Stopwatch]::StartNew()

if ($PSVersionTable.PSVersion.Major -ge 7) {
  $results = 1..$Concurrent | ForEach-Object -Parallel {
    $ok = 0
    $fail = 0
    foreach ($i in 1..$using:perWorker) {
      try {
        $r = Invoke-WebRequest -Uri "$using:BaseUrl/health" -UseBasicParsing -TimeoutSec 30
        if ($r.StatusCode -eq 200) { $ok++ } else { $fail++ }
      } catch {
        $fail++
      }
    }
    @{ ok = $ok; fail = $fail }
  } -ThrottleLimit $Concurrent
  $okTotal = ($results | ForEach-Object { $_.ok } | Measure-Object -Sum).Sum
  $failTotal = ($results | ForEach-Object { $_.fail } | Measure-Object -Sum).Sum
} else {
  Write-Host "PowerShell 7+ recommended for parallel load. Running sequential fallback."
  $okTotal = 0
  $failTotal = 0
  foreach ($i in 1..$actualTotal) {
    try {
      $r = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 30
      if ($r.StatusCode -eq 200) { $okTotal++ } else { $failTotal++ }
    } catch {
      $failTotal++
    }
  }
}

$sw.Stop()

Write-Host "Completed in $($sw.ElapsedMilliseconds) ms"
Write-Host "OK: $okTotal  Fail: $failTotal"
if ($okTotal -gt 0 -and $sw.ElapsedMilliseconds -gt 0) {
  $rps = [math]::Round($okTotal / ($sw.ElapsedMilliseconds / 1000.0), 2)
  Write-Host "Approx successful RPS (health only): $rps"
}
