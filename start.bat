@echo off
chcp 65001 >nul
title OmniVox Caster

if not exist "venv\Scripts\activate.bat" (
    echo  [FEHLER] Virtuelle Umgebung nicht gefunden.
    echo  Bitte zuerst install.bat ausfuehren!
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"
python main_overlay.py
