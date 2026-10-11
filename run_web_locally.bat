@echo off
title Web version on this PC
cd /d "%~dp0web"
echo Opening http://localhost:8000 ... (close this window to stop)
start "" http://localhost:8000
python dev_server.py
pause
