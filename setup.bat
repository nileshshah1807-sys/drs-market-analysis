@echo off
echo ============================================================
echo DR. NILESH SHAH'S MARKET ANALYSIS - Setup Script
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Download Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/4] Installing required packages...
echo.

python -m pip install yfinance pandas numpy ta openpyxl pdfplumber reportlab schedule Pillow matplotlib requests keyring --quiet

echo.
echo [2/4] Verifying installation...
echo.

python -c "
import yfinance; print('[OK] yfinance')
import pandas; print('[OK] pandas')
import numpy; print('[OK] numpy')
import ta; print('[OK] ta (technical analysis)')
import openpyxl; print('[OK] openpyxl')
import reportlab; print('[OK] reportlab')
import schedule; print('[OK] schedule')
print()
print('All packages installed successfully!')
"

echo.
echo [3/4] Checking files...
echo.

if exist dr_shah_analysis.py (
    echo [OK] dr_shah_analysis.py found
) else (
    echo [ERROR] dr_shah_analysis.py NOT found!
    echo Please make sure all files are in the same folder.
    pause
    exit /b 1
)

if exist daily_report.py (
    echo [OK] daily_report.py found
) else (
    echo [ERROR] daily_report.py NOT found!
    echo Please make sure all files are in the same folder.
    pause
    exit /b 1
)

if exist scoring.py (
    echo [OK] scoring.py found
) else (
    echo [ERROR] scoring.py NOT found!
    echo Please make sure all files are in the same folder.
    pause
    exit /b 1
)

if exist ui_theme.py (
    echo [OK] ui_theme.py found
) else (
    echo [ERROR] ui_theme.py NOT found!
    echo Please make sure all files are in the same folder.
    pause
    exit /b 1
)

if exist pattern_recognition.py (
    echo [OK] pattern_recognition.py found
) else (
    echo [WARNING] pattern_recognition.py not found - Pattern features disabled
)

if exist logo_new.png (
    echo [OK] logo_new.png found
) else (
    echo [WARNING] logo_new.png not found
)

echo.
echo [4/4] Setup Complete!
echo.
echo ============================================================
echo To run the app: python dr_shah_analysis.py
echo Or double-click: run_app.bat
echo ============================================================
echo.
pause
