@echo off
echo Starting OU Chatbot (backend + frontend)...

start "Backend  :8000" /D "%~dp0backend" cmd /k ".venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul
start "Frontend :5173" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo  Backend  -> http://localhost:8000
echo  Frontend -> http://localhost:5173
echo.
echo Two command windows opened. Close them to stop the servers.
