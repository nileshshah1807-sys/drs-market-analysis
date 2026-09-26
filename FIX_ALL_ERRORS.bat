@echo off
title DR. NILESH SHAH'S MARKET ANALYSIS - Complete Fix
color 0A
echo ============================================================
echo DR. NILESH SHAH'S MARKET ANALYSIS - COMPLETE FIX
echo ============================================================
echo.
echo This script will fix ALL errors and install everything needed.
echo.

REM Change to script directory
cd /d "%~dp0"

echo [STEP 1] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! 
    echo Download from: https://www.python.org/downloads/
    echo Make sure to CHECK "Add Python to PATH" during install!
    pause
    exit /b 1
)
python --version
echo.

echo [STEP 2] Upgrading pip...
python -m pip install --upgrade pip
echo.

echo [STEP 3] Installing ALL required packages...
echo.

echo Installing yfinance...
pip install yfinance --quiet
if errorlevel 1 (
    echo Retrying with --user flag...
    pip install yfinance --user --quiet
)

echo Installing pandas...
pip install pandas --quiet
if errorlevel 1 pip install pandas --user --quiet

echo Installing numpy...
pip install numpy --quiet
if errorlevel 1 pip install numpy --user --quiet

echo Installing ta (Technical Analysis Library)...
pip install ta --quiet
if errorlevel 1 pip install ta --user --quiet

echo Installing scikit-learn...
pip install scikit-learn --quiet
if errorlevel 1 pip install scikit-learn --user --quiet

echo Installing openpyxl...
pip install openpyxl --quiet
if errorlevel 1 pip install openpyxl --user --quiet

echo Installing reportlab...
pip install reportlab --quiet
if errorlevel 1 pip install reportlab --user --quiet

echo Installing pdfplumber...
pip install pdfplumber --quiet
if errorlevel 1 pip install pdfplumber --user --quiet

echo Installing schedule...
pip install schedule --quiet
if errorlevel 1 pip install schedule --user --quiet

echo Installing Pillow...
pip install Pillow --quiet
if errorlevel 1 pip install Pillow --user --quiet

echo Installing pytz...
pip install pytz --quiet
if errorlevel 1 pip install pytz --user --quiet

echo.
echo [STEP 4] Verifying installation...
echo.

python -c "
import sys
print(f'Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')
print()

modules = {
    'yfinance': 'Yahoo Finance Data',
    'pandas': 'Data Processing',
    'numpy': 'Numerical Computing', 
    'ta': 'Technical Analysis',
    'sklearn': 'Machine Learning',
    'openpyxl': 'Excel Support',
    'reportlab': 'PDF Generation',
    'pdfplumber': 'PDF Reading',
    'schedule': 'Task Scheduling',
    'PIL': 'Image Processing',
    'pytz': 'Timezone Support'
}

failed = []
for module, name in modules.items():
    try:
        __import__(module)
        print(f'  [OK] {name}')
    except ImportError:
        print(f'  [FAIL] {name} - {module}')
        failed.append(module)

print()
if failed:
    print(f'FAILED: {', '.join(failed)}')
    print('Run this manually:')
    print(f'  pip install {' '.join(failed)}')
else:
    print('ALL PACKAGES INSTALLED SUCCESSFULLY!')
"

echo.
echo [STEP 5] Checking app files...
echo.

set MISSING=0
if exist dr_shah_analysis.py (echo [OK] dr_shah_analysis.py) else (echo [MISSING] dr_shah_analysis.py & set MISSING=1)
if exist daily_report.py (echo [OK] daily_report.py) else (echo [MISSING] daily_report.py & set MISSING=1)
if exist ai_engine.py (echo [OK] ai_engine.py) else (echo [MISSING] ai_engine.py & set MISSING=1)
if exist pattern_recognition.py (echo [OK] pattern_recognition.py) else (echo [MISSING] pattern_recognition.py & set MISSING=1)
if exist live_trading.py (echo [OK] live_trading.py) else (echo [MISSING] live_trading.py & set MISSING=1)
if exist logo_new.png (echo [OK] logo_new.png) else (echo [WARNING] logo_new.png not found)

if %MISSING%==1 (
    echo.
    echo ERROR: Some app files are missing!
    echo Make sure ALL .py files are in this folder.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SUCCESS! All dependencies installed and files verified!
echo.
echo To run the app: python dr_shah_analysis.py
echo Or double-click: run_app.bat
echo ============================================================
echo.
pause
