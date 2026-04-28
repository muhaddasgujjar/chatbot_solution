param(
  [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "== OU Chatbot full verification starting =="

Write-Host "[1/4] Backend unit/API tests"
Push-Location "D:/projects/chatbot_solution/backend"
try {
  .\.venv\Scripts\python -m pytest -q
} finally {
  Pop-Location
}

Write-Host "[2/4] Frontend production build"
Push-Location "D:/projects/chatbot_solution/frontend"
try {
  npm run build
} finally {
  Pop-Location
}

Write-Host "[3/4] Backend runtime smoke script"
$backendProc = Start-Process -FilePath "D:/projects/chatbot_solution/backend/.venv/Scripts/python.exe" -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory "D:/projects/chatbot_solution/backend" -PassThru
try {
  Start-Sleep -Seconds 20
  powershell -ExecutionPolicy Bypass -File "D:/projects/chatbot_solution/scripts/smoke-test.ps1" -ApiBaseUrl $BackendUrl
} finally {
  Stop-Process -Id $backendProc.Id -ErrorAction SilentlyContinue
}

Write-Host "[4/4] Verification completed successfully."
