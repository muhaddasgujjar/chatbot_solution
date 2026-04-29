param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173,
  [switch]$UpdateFrontendEnv = $true,
  [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

function Test-PortAvailable {
  param([int]$Port)
  $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  return -not $listener
}

function Get-FreePort {
  param([int]$StartPort)
  $port = $StartPort
  while ($port -lt ($StartPort + 200)) {
    if (Test-PortAvailable -Port $port) {
      return $port
    }
    $port++
  }
  throw "Could not find an available port near $StartPort."
}

function Set-FrontendApiBaseUrl {
  param(
    [string]$FrontendEnvPath,
    [string]$ApiBaseUrl
  )

  if (Test-Path $FrontendEnvPath) {
    $lines = Get-Content -Path $FrontendEnvPath
    $updated = $false
    $newLines = @()
    foreach ($line in $lines) {
      if ($line -match "^VITE_API_BASE_URL=") {
        $newLines += "VITE_API_BASE_URL=$ApiBaseUrl"
        $updated = $true
      } else {
        $newLines += $line
      }
    }
    if (-not $updated) {
      $newLines += "VITE_API_BASE_URL=$ApiBaseUrl"
    }
    Set-Content -Path $FrontendEnvPath -Value $newLines
  } else {
    Set-Content -Path $FrontendEnvPath -Value @("VITE_API_BASE_URL=$ApiBaseUrl")
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

$selectedBackendPort = Get-FreePort -StartPort $BackendPort
$selectedFrontendPort = Get-FreePort -StartPort $FrontendPort
if ($selectedFrontendPort -eq $selectedBackendPort) {
  $selectedFrontendPort = Get-FreePort -StartPort ($selectedFrontendPort + 1)
}

$apiBaseUrl = "http://127.0.0.1:$selectedBackendPort"

Write-Host "Resolved backend port: $selectedBackendPort"
Write-Host "Resolved frontend port: $selectedFrontendPort"
Write-Host "API base URL: $apiBaseUrl"

if ($UpdateFrontendEnv) {
  $frontendEnvPath = Join-Path $frontendDir ".env"
  Set-FrontendApiBaseUrl -FrontendEnvPath $frontendEnvPath -ApiBaseUrl $apiBaseUrl
  Write-Host "Updated frontend .env with VITE_API_BASE_URL=$apiBaseUrl"
}

$backendCmd = ".\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $selectedBackendPort"
$frontendCmd = "npm run dev -- --host 127.0.0.1 --port $selectedFrontendPort"

Write-Host ""
Write-Host "Backend command:"
Write-Host "  $backendCmd"
Write-Host "Frontend command:"
Write-Host "  $frontendCmd"

if ($DryRun) {
  Write-Host ""
  Write-Host "DryRun enabled: no processes were started."
  exit 0
}

Start-Process -WorkingDirectory $backendDir -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $backendCmd | Out-Null
Start-Process -WorkingDirectory $frontendDir -FilePath "powershell" -ArgumentList "-NoExit", "-Command", $frontendCmd | Out-Null

Write-Host ""
Write-Host "Started backend and frontend in separate PowerShell windows."
