@echo off
chcp 65001 >nul
title OmniVox Caster

cd /d "%~dp0"
set LOG_FILE=%~dp0startup.log

if not exist "venv\Scripts\python.exe" (
    echo  [FEHLER] Virtuelle Umgebung nicht gefunden.
    echo  Bitte zuerst install.bat ausfuehren!
    pause
    exit /b 1
)

echo  [%date% %time%] Starte OmniVox Caster ... > "%LOG_FILE%"
echo  Projektpfad: %CD% >> "%LOG_FILE%"

venv\Scripts\python.exe -u main_overlay.py >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo  [FEHLER] Die App wurde mit Exit-Code %EXIT_CODE% beendet.
    echo  Details stehen in:
    echo  %LOG_FILE%
    echo.
    type "%LOG_FILE%"
    echo.
    pause
    exit /b %EXIT_CODE%
)
