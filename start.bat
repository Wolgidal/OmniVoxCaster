@echo off
chcp 65001 >nul
title OmniVox Caster

cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
    echo  [FEHLER] Virtuelle Umgebung nicht gefunden.
    echo  Bitte zuerst install.bat ausfuehren!
    pause
    exit /b 1
)

start "" /b venv\Scripts\pythonw.exe main_overlay.py
exit /b 0
