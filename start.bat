@echo off
chcp 65001 >nul
echo ========================================
echo   ColorFlow Web - Service Launcher
echo ========================================
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please create one with: python -m venv .venv
    pause
    exit /b 1
)

echo [INFO] Starting Flask dev server...
echo [INFO] Server will be available at http://127.0.0.1:5000
echo.

REM Start the Flask app
.venv\Scripts\python.exe app.py

pause
