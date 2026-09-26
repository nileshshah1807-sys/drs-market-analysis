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

pip install yfinance pandas numpy ta scikit-learn openpyxl pdfplumber reportlab schedule Pillow --quiet

echo.
echo [2/4] Verifying installation...
echo.

python -c "
import yfinance; print('[OK] yfinance')
import pandas; print('[OK] pandas')
import numpy; print('[OK] numpy')
import ta; print('[OK] ta (technical analysis)')
import sklearn; print('[OK] scikit-learn')
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

if exist ai_engine.py (
    echo [OK] ai_engine.py found
) else (
    echo [WARNING] ai_engine.py not found - AI features disabled
)

if exist pattern_recognition.py (
    echo [OK] pattern_recognition.py found
) else (
    echo [WARNING] pattern_recognition.py not found - Pattern features disabled
)

if exist live_trading.py (
    echo [OK] live_trading.py found
) else (
    echo [WARNING] live_trading.py not found - Live trading disabled
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
