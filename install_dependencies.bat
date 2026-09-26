@echo off
echo ============================================================
echo DR. NILESH SHAH'S MARKET ANALYSIS
echo Installing All Dependencies...
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

echo [1/8] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/8] Installing yfinance...
python -m pip install yfinance --quiet

echo [3/8] Installing pandas and numpy...
python -m pip install pandas numpy --quiet

echo [4/8] Installing ta (Technical Analysis)...
python -m pip install ta --quiet

echo [5/8] Installing scikit-learn (AI/ML)...
python -m pip install scikit-learn --quiet

echo [6/8] Installing openpyxl, reportlab, pdfplumber...
python -m pip install openpyxl reportlab pdfplumber --quiet

echo [7/8] Installing schedule, Pillow, matplotlib, requests, keyring...
python -m pip install schedule Pillow matplotlib requests keyring --quiet

echo [8/8] Installing pytz (timezone support)...
python -m pip install pytz --quiet

echo.
echo ============================================================
echo Verifying Installation...
echo ============================================================
echo.

python -c "
import sys
print(f'Python: {sys.version}')
print()

modules = [
    ('yfinance', 'Stock data'),
    ('pandas', 'Data processing'),
    ('numpy', 'Numerical computing'),
    ('ta', 'Technical analysis'),
    ('sklearn', 'Machine learning'),
    ('openpyxl', 'Excel support'),
    ('reportlab', 'PDF generation'),
    ('pdfplumber', 'PDF reading'),
    ('schedule', 'Auto scheduling'),
    ('PIL', 'Image support'),
    ('pytz', 'Timezone support'),
    ('matplotlib', 'Charts'),
    ('requests', 'NSE/BSE data'),
    ('keyring', 'Secure password storage'),
]

all_ok = True
for module, name in modules:
    try:
        __import__(module)
        print(f'[OK] {name} ({module})')
    except ImportError:
        print(f'[MISSING] {name} ({module})')
        all_ok = False

print()
if all_ok:
    print('ALL PACKAGES INSTALLED SUCCESSFULLY!')
else:
    print('Some packages are missing. Please install manually.')
"

echo.
echo ============================================================
echo Checking App Files...
echo ============================================================
echo.

if exist dr_shah_analysis.py (echo [OK] dr_shah_analysis.py) else (echo [MISSING] dr_shah_analysis.py)
if exist daily_report.py (echo [OK] daily_report.py) else (echo [MISSING] daily_report.py)
if exist ai_engine.py (echo [OK] ai_engine.py) else (echo [MISSING] ai_engine.py)
if exist pattern_recognition.py (echo [OK] pattern_recognition.py) else (echo [MISSING] pattern_recognition.py)
if exist live_trading.py (echo [OK] live_trading.py) else (echo [MISSING] live_trading.py)
if exist logo_new.png (echo [OK] logo_new.png) else (echo [MISSING] logo_new.png)

echo.
echo ============================================================
echo Setup Complete!
echo.
echo To run the app: python dr_shah_analysis.py
echo Or double-click: run_app.bat
echo ============================================================
echo.
pause
