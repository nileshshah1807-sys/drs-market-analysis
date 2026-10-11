@echo off
title Put the web version online (Vercel)
cd /d "%~dp0web"
python deploy.py
echo.
pause
