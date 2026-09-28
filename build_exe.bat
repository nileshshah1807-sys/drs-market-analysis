@echo off
title Build DR. NILESH SHAH'S MARKET ANALYSIS .exe
cd /d "%~dp0"
echo ============================================================
echo  Building "DR Nilesh Shah Market Analysis.exe"
echo ============================================================
echo.

tasklist /FI "IMAGENAME eq DR Nilesh Shah Market Analysis.exe" 2>nul | find /I "DR Nilesh Shah Market Analysis.exe" >nul
if not errorlevel 1 (
    echo The app is running. Close it first, then run this again.
    pause
    exit /b 1
)

echo [1/3] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1 || python -m pip install pyinstaller --quiet

echo [2/3] Building (takes about 2 minutes)...
rem Build in the temp folder so OneDrive doesn't sync ~250 MB of build files
python -m PyInstaller DR_Nilesh_Shah_Market_Analysis.spec --noconfirm --log-level WARN --workpath "%TEMP%\drs_build" --distpath "%TEMP%\drs_dist"
if errorlevel 1 (
    echo.
    echo BUILD FAILED - see the messages above.
    pause
    exit /b 1
)

echo [3/3] Installing into this folder...
if exist "_internal" rmdir /s /q "_internal"
robocopy "%TEMP%\drs_dist\DR Nilesh Shah Market Analysis" "." /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo COPY FAILED.
    pause
    exit /b 1
)

echo.
echo Done! Double-click "DR Nilesh Shah Market Analysis.exe" to start the app.
pause
