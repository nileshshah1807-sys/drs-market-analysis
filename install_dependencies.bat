@echo off
echo ============================================================
echo DR. NILESH SHAH'S MARKET ANALYSIS
echo Installing All Dependencies...
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

echo [1/7] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/7] Installing yfinance...
python -m pip install yfinance --quiet

echo [3/7] Installing pandas and numpy...
python -m pip install pandas numpy --quiet

echo [4/7] Installing ta (Technical Analysis)...
python -m pip install ta --quiet

echo [5/7] Installing openpyxl, reportlab, pdfplumber...
python -m pip install openpyxl reportlab pdfplumber --quiet

echo [6/7] Installing schedule, Pillow, matplotlib, requests, keyring...
python -m pip install schedule Pillow matplotlib requests keyring --quiet

echo [7/7] Installing pytz (timezone support)...
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
if exist scoring.py (echo [OK] scoring.py) else (echo [MISSING] scoring.py)
if exist ui_theme.py (echo [OK] ui_theme.py) else (echo [MISSING] ui_theme.py)
if exist market_data.py (echo [OK] market_data.py) else (echo [MISSING] market_data.py)
if exist pattern_recognition.py (echo [OK] pattern_recognition.py) else (echo [MISSING] pattern_recognition.py)
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
