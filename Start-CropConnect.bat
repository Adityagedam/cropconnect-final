@echo off
REM CropConnect Application Launcher
REM This script starts both backend and frontend servers

cd /d "%~dp0"

REM Start backend in a new window
start "CropConnect Backend" cmd /k ""%~dp0cropconnect-backend\run-backend.cmd""

REM Wait a moment for backend to start
timeout /t 3 /nobreak

REM Start frontend in a new window
start "CropConnect Frontend" cmd /k ""%~dp0cropconnect-frontend\run-frontend.cmd""

REM Wait for frontend to compile
timeout /t 10 /nobreak

REM Open the application in default browser
start http://localhost:3000

REM Display status message
cls
echo.
echo ========================================
echo   CropConnect Application Started
echo ========================================
echo.
echo Frontend:  http://localhost:3000
echo Backend:   http://localhost:8001
echo.
echo Close this window when done. The servers
echo will continue running in separate windows.
echo.
pause
