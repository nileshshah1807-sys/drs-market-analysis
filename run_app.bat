@echo off
title DR. NILESH SHAH'S MARKET ANALYSIS
echo ============================================================
echo DR. NILESH SHAH'S MARKET ANALYSIS
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Run the smart launcher that auto-installs dependencies
python start_app.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ERROR: Application failed to start!
    echo.
    echo Try running: python install_dependencies.bat
    echo Then try again.
    echo ============================================================
    pause
)
