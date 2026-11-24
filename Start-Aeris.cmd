@echo off
cd /d "%~dp0"
python tools\start.py
if errorlevel 1 pause
