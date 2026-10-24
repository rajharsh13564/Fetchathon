@echo off
REM FinancePilot AI - Quick Start Script for Windows

set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

echo 🚀 FinancePilot AI - Starting up...

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies if needed
if not exist "venv\.installed" (
    echo 📦 Installing Python dependencies...
    pip install -r requirements.txt
    type nul > venv\.installed
)

REM Check for .env file
if not exist ".env" (
    echo ⚠️  No .env file found. Copying from .env.example...
    copy .env.example .env
    echo 📝 Please edit .env and add your GEMINI_API_KEY
    echo    Then run this script again.
    pause
    exit /b 1
)

REM Check for Gemini API key
findstr /C:"GEMINI_API_KEY=your_gemini_api_key_here" .env >nul
if %errorlevel% equ 0 (
    echo ⚠️  Please set your GEMINI_API_KEY in .env file
    pause
    exit /b 1
)

REM Install frontend dependencies if needed
if not exist "frontend\node_modules" (
    echo 📦 Installing frontend dependencies...
    cd frontend && npm install && cd ..
)

echo ✅ Setup complete!
echo.
echo To start the application:
echo   Terminal 1: make run-backend    (starts API on http://localhost:8000)
echo   Terminal 2: make run-frontend   (starts UI on http://localhost:5173)
echo.
echo For full multi-agent mode (4 additional terminals):
echo   make run-orchestrator
echo   make run-quant-screener
echo   make run-risk-manager
echo   make run-deep-researcher
echo.
echo Run tests: make test
echo View docs: open docs\architecture.md
pause