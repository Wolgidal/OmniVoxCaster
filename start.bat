@echo off
chcp 65001 >nul
title OmniVox Caster

if not exist "venv\Scripts\activate.bat" (
    echo  [FEHLER] Virtuelle Umgebung nicht gefunden.
    echo  Bitte zuerst install.bat ausfuehren!
    pause
    exit /b 1
)

start "" "venv\Scripts\pythonw.exe" main_overlay.py
