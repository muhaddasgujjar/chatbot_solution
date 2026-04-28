param(
  [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

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

Write-Host "Smoke test completed."
