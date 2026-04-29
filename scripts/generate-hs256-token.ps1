param(
  [string]$Subject = "demo-user",
  [string]$Issuer = "https://login.microsoftonline.com/tenant/v2.0",
  [string]$Audience = "ou-chatbot-api",
  [string]$Secret = "",
  [string[]]$Groups = @("student"),
  [int]$ExpiresInSeconds = 3600,
  [switch]$WriteToFrontendEnv = $false
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Secret)) {
  throw "Secret is required. Pass -Secret <value> (should match ENTRA_TEST_HS256_SECRET)."
}

$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$exp = $now + $ExpiresInSeconds

$headerJson = '{"alg":"HS256","typ":"JWT"}'
$groupsJson = ($Groups | ForEach-Object { '"' + $_ + '"' }) -join ","
$payloadJson = '{"sub":"' + $Subject + '","iss":"' + $Issuer + '","aud":"' + $Audience + '","iat":' + $now + ',"exp":' + $exp + ',"department":"' + ($(if ($Groups -contains "faculty") { "Engineering Faculty" } else { "Student Affairs" })) + '","jobTitle":"' + ($(if ($Groups -contains "faculty") { "Professor" } else { "Student" })) + '","groups":[' + $groupsJson + ']}'

function ConvertTo-Base64Url([byte[]]$bytes) {
  [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$headerEncoded = ConvertTo-Base64Url ([System.Text.Encoding]::UTF8.GetBytes($headerJson))
$payloadEncoded = ConvertTo-Base64Url ([System.Text.Encoding]::UTF8.GetBytes($payloadJson))
$signingInput = "$headerEncoded.$payloadEncoded"

$hmac = [System.Security.Cryptography.HMACSHA256]::new([System.Text.Encoding]::UTF8.GetBytes($Secret))
try {
  $signature = $hmac.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($signingInput))
} finally {
  $hmac.Dispose()
}
$signatureEncoded = ConvertTo-Base64Url $signature
$token = "$signingInput.$signatureEncoded"

if ($WriteToFrontendEnv) {
  $repoRoot = Split-Path -Parent $PSScriptRoot
  $frontendEnvPath = Join-Path $repoRoot "frontend\.env"
  if (Test-Path $frontendEnvPath) {
    $lines = Get-Content -Path $frontendEnvPath
  } else {
    $lines = @()
  }

  $updated = $false
  $nextLines = @()
  foreach ($line in $lines) {
    if ($line -match "^VITE_DEMO_BEARER_TOKEN=") {
      $nextLines += "VITE_DEMO_BEARER_TOKEN=$token"
      $updated = $true
    } else {
      $nextLines += $line
    }
  }
  if (-not $updated) {
    $nextLines += "VITE_DEMO_BEARER_TOKEN=$token"
  }
  Set-Content -Path $frontendEnvPath -Value $nextLines
  Write-Host "Updated frontend/.env VITE_DEMO_BEARER_TOKEN"
}

Write-Host "HS256 token generated:"
Write-Output $token
