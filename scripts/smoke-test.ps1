param(
  [string]$ApiBaseUrl = "http://127.0.0.1:8000",
  [switch]$IncludeIntegrations = $true,
  [switch]$IncludeLiveIntegrations = $false,
  [switch]$IncludeAuthChecks = $false
)

$ErrorActionPreference = "Stop"

function Get-EnvValueFromFile {
  param(
    [string]$Path,
    [string]$Key
  )

  if (-not (Test-Path $Path)) {
    return ""
  }

  $line = Get-Content -Path $Path | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
  if (-not $line) {
    return ""
  }
  return ($line -replace "^$Key=", "").Trim()
}

function New-Hs256JwtToken {
  param(
    [string]$Subject,
    [string]$Issuer,
    [string]$Audience,
    [string]$Secret,
    [string[]]$Groups,
    [int]$ExpiresInSeconds = 300
  )

  $groupsJson = ($Groups | ForEach-Object { '"' + $_ + '"' }) -join ","
  $pythonScript = @"
import base64
import hashlib
import hmac
import json
import sys
import time

subject = sys.argv[1]
issuer = sys.argv[2]
audience = sys.argv[3]
secret = sys.argv[4].encode("utf-8")
groups = [g for g in sys.argv[5].split(",") if g]
expires_in = int(sys.argv[6])

now = int(time.time())
header = {"alg": "HS256", "typ": "JWT"}
payload = {
    "sub": subject,
    "iss": issuer,
    "aud": audience,
    "iat": now,
    "exp": now + expires_in,
    "department": "Engineering Faculty" if "faculty" in groups else "Student Affairs",
    "jobTitle": "Professor" if "faculty" in groups else "Student",
    "groups": groups,
}

def b64(data):
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")

encoded_header = b64(header)
encoded_payload = b64(payload)
signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("utf-8")
print(f"{encoded_header}.{encoded_payload}.{encoded_signature}")
"@

  $groupsCsv = $Groups -join ","
  $token = & "D:/projects/chatbot_solution/backend/.venv/Scripts/python.exe" -c $pythonScript $Subject $Issuer $Audience $Secret $groupsCsv $ExpiresInSeconds
  return $token.Trim()
}

Write-Host "Smoke test starting against $ApiBaseUrl"

$health = Invoke-WebRequest -UseBasicParsing "$ApiBaseUrl/health"
Write-Host "Health status:" $health.StatusCode

$ingestBody = '{"urls":["https://support.oakland.edu"],"role_access":"all"}'
$ingest = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/ingest" -Method POST -ContentType "application/json" -Body $ingestBody
Write-Host "Ingest status:" $ingest.StatusCode

$chatBody = '{"query":"How can I contact IT support?","user_id":"smoke-script-user","role":"all"}'
$chat = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/chat" -Method POST -ContentType "application/json" -Body $chatBody
Write-Host "Chat status:" $chat.StatusCode
Write-Host "Chat payload preview:"
Write-Host ($chat.Content.Substring(0, [Math]::Min(240, $chat.Content.Length)))

if ($IncludeIntegrations) {
  Write-Host "Running integration contract smoke checks..."

  $tdxSearchBody = '{"query":"password reset"}'
  $tdxSearch = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/tdx/articles/search" -Method POST -ContentType "application/json" -Body $tdxSearchBody
  Write-Host "TDX article search status:" $tdxSearch.StatusCode
  $tdxSearchJson = $tdxSearch.Content | ConvertFrom-Json
  if (-not ($tdxSearchJson.PSObject.Properties.Name -contains "enabled")) {
    throw "TDX article search payload missing 'enabled'."
  }
  if (-not ($tdxSearchJson.PSObject.Properties.Name -contains "results")) {
    throw "TDX article search payload missing 'results'."
  }

  $tdxTicketBody = '{"title":"Smoke Test Ticket","description":"Automated smoke test ticket payload for integration validation.","requester_email":"smoke@example.edu","priority":"normal","category":"general"}'
  $tdxTicket = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/tdx/tickets/create" -Method POST -ContentType "application/json" -Body $tdxTicketBody
  Write-Host "TDX ticket create status:" $tdxTicket.StatusCode
  $tdxTicketJson = $tdxTicket.Content | ConvertFrom-Json
  if (-not ($tdxTicketJson.PSObject.Properties.Name -contains "enabled")) {
    throw "TDX ticket create payload missing 'enabled'."
  }
  if (-not ($tdxTicketJson.PSObject.Properties.Name -contains "ticket")) {
    throw "TDX ticket create payload missing 'ticket'."
  }

  $handoffBody = '{"user_id":"smoke-script-user","transcript":["Hello","Need live support"]}'
  $handoff = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/purechat/handoff" -Method POST -ContentType "application/json" -Body $handoffBody
  Write-Host "PureChat handoff status:" $handoff.StatusCode
  $handoffJson = $handoff.Content | ConvertFrom-Json
  if (-not ($handoffJson.PSObject.Properties.Name -contains "handoff")) {
    throw "PureChat handoff payload missing 'handoff'."
  }
}

if ($IncludeLiveIntegrations) {
  Write-Host "Running live integration checks (config-aware)..."
  $repoRoot = Split-Path -Parent $PSScriptRoot
  $backendEnvPath = Join-Path $repoRoot "backend\.env"
  $tdxBaseUrl = Get-EnvValueFromFile -Path $backendEnvPath -Key "TDX_BASE_URL"
  $tdxApiToken = Get-EnvValueFromFile -Path $backendEnvPath -Key "TDX_API_TOKEN"
  $purechatWidgetId = Get-EnvValueFromFile -Path $backendEnvPath -Key "PURECHAT_WIDGET_ID"

  if ([string]::IsNullOrWhiteSpace($tdxBaseUrl) -or [string]::IsNullOrWhiteSpace($tdxApiToken)) {
    Write-Host "Skipping live TDX checks: TDX_BASE_URL/TDX_API_TOKEN not configured in backend/.env."
  } else {
    $liveSearchBody = '{"query":"student account access"}'
    $liveSearch = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/tdx/articles/search" -Method POST -ContentType "application/json" -Body $liveSearchBody
    $liveSearchJson = $liveSearch.Content | ConvertFrom-Json
    if (-not $liveSearchJson.enabled) {
      throw "Live TDX article search returned enabled=false while TDX is configured."
    }

    $liveTicketBody = '{"title":"Live Smoke Ticket","description":"Live integration smoke check for TDX ticket creation.","requester_email":"smoke@example.edu","priority":"normal","category":"general"}'
    $liveTicket = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/tdx/tickets/create" -Method POST -ContentType "application/json" -Body $liveTicketBody
    $liveTicketJson = $liveTicket.Content | ConvertFrom-Json
    if (-not $liveTicketJson.enabled) {
      throw "Live TDX ticket create returned enabled=false while TDX is configured."
    }
  }

  if ([string]::IsNullOrWhiteSpace($purechatWidgetId)) {
    Write-Host "Skipping live PureChat checks: PURECHAT_WIDGET_ID not configured in backend/.env."
  } else {
    $liveHandoffBody = '{"user_id":"smoke-script-user","transcript":["Need live support now"]}'
    $liveHandoff = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/purechat/handoff" -Method POST -ContentType "application/json" -Body $liveHandoffBody
    $liveHandoffJson = $liveHandoff.Content | ConvertFrom-Json
    if (-not $liveHandoffJson.enabled) {
      throw "Live PureChat handoff returned enabled=false while PURECHAT_WIDGET_ID is configured."
    }
  }
}

if ($IncludeAuthChecks) {
  Write-Host "Running auth and RBAC smoke checks..."
  $repoRoot = Split-Path -Parent $PSScriptRoot
  $backendEnvPath = Join-Path $repoRoot "backend\.env"
  $authEnabled = (Get-EnvValueFromFile -Path $backendEnvPath -Key "AUTH_ENABLED").ToLower()
  $issuer = Get-EnvValueFromFile -Path $backendEnvPath -Key "ENTRA_ISSUER"
  $audience = Get-EnvValueFromFile -Path $backendEnvPath -Key "ENTRA_AUDIENCE"
  $algorithms = (Get-EnvValueFromFile -Path $backendEnvPath -Key "ENTRA_JWT_ALGORITHMS").ToUpper()
  $secret = Get-EnvValueFromFile -Path $backendEnvPath -Key "ENTRA_TEST_HS256_SECRET"

  if ($authEnabled -ne "true") {
    Write-Host "Skipping auth checks: AUTH_ENABLED is not true in backend/.env."
  } elseif ($algorithms -notmatch "HS256") {
    Write-Host "Skipping auth checks: ENTRA_JWT_ALGORITHMS does not include HS256."
  } elseif ([string]::IsNullOrWhiteSpace($issuer) -or [string]::IsNullOrWhiteSpace($audience) -or [string]::IsNullOrWhiteSpace($secret)) {
    Write-Host "Skipping auth checks: ENTRA_ISSUER/ENTRA_AUDIENCE/ENTRA_TEST_HS256_SECRET must be configured."
  } else {
    $studentToken = New-Hs256JwtToken -Subject "smoke-student" -Issuer $issuer -Audience $audience -Secret $secret -Groups @("student")
    $facultyToken = New-Hs256JwtToken -Subject "smoke-faculty" -Issuer $issuer -Audience $audience -Secret $secret -Groups @("faculty")

    $authChatBody = '{"query":"Need help with wifi","user_id":"smoke-student","role":"student"}'
    $authChat = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/chat" -Method POST -ContentType "application/json" -Headers @{ Authorization = "Bearer $studentToken" } -Body $authChatBody
    Write-Host "Auth chat status:" $authChat.StatusCode
    if ($authChat.StatusCode -ne 200) {
      throw "Auth chat validation failed."
    }

    $rbacDenyBody = '{"title":"Student ticket request","description":"Student should be blocked by RBAC.","requester_email":"student@example.edu","priority":"normal","category":"general"}'
    try {
      Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/tdx/tickets/create" -Method POST -ContentType "application/json" -Headers @{ Authorization = "Bearer $studentToken" } -Body $rbacDenyBody
      throw "RBAC check failed: student request unexpectedly succeeded."
    } catch {
      if (-not $_.Exception.Response -or $_.Exception.Response.StatusCode.value__ -ne 403) {
        throw "RBAC check failed: expected 403 for student role."
      }
      Write-Host "RBAC student deny status: 403"
    }

    $rbacAllowBody = '{"title":"Faculty ticket request","description":"Faculty request should pass RBAC policy.","requester_email":"faculty@example.edu","priority":"normal","category":"general"}'
    $rbacAllow = Invoke-WebRequest -UseBasicParsing -Uri "$ApiBaseUrl/api/integrations/tdx/tickets/create" -Method POST -ContentType "application/json" -Headers @{ Authorization = "Bearer $facultyToken" } -Body $rbacAllowBody
    Write-Host "RBAC faculty allow status:" $rbacAllow.StatusCode
    if ($rbacAllow.StatusCode -ne 200) {
      throw "RBAC check failed: faculty request did not succeed."
    }
  }
}

Write-Host "Smoke test completed."
