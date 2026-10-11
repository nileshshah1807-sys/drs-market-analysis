@echo off
title Publish the web version (GitHub - Vercel)
cd /d "%~dp0web"
python deploy.py
echo.
pause
