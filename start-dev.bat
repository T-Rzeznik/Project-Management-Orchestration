@echo off
title Orchestration Framework - Dev Launcher
cd /d "%~dp0"

echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)

echo Installing frontend dependencies...
cd frontend
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed
    pause
    exit /b 1
)
cd ..

echo Starting FastAPI backend on http://localhost:8000 ...
start "FastAPI Backend" cmd /k "cd /d "%~dp0" && python -m uvicorn api.server:app --reload --port 8000"

echo Starting React frontend on http://localhost:5173 ...
start "React Frontend" cmd /k "cd /d "%~dp0\frontend" && npm run dev"

echo Waiting for frontend to start...
timeout /t 5 /nobreak >nul

echo Opening browser...
start http://localhost:5173

echo.
echo All services launched. Close the backend and frontend terminal windows to stop them.
