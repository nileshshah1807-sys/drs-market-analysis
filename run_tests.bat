@echo off
title Test DR. NILESH SHAH'S MARKET ANALYSIS
cd /d "%~dp0"
echo ============================================================
echo  Full automatic test of every feature (about 10 minutes)
echo  Runs on a throwaway copy - your data, email and Windows
echo  task are not touched. Needs internet.
echo ============================================================
python tests\run_deep_test.py --both
echo.
pause
