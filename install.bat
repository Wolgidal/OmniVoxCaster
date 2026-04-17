@echo off
chcp 65001 >nul
title OmniVox Caster — Installation

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║   OmniVox Caster — Voxcaster Imperialis          ║
echo  ║   Installation                                    ║
echo  ╚══════════════════════════════════════════════════╝
echo.

:: Python prüfen
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Python wurde nicht gefunden.
    echo  Bitte installiere Python 3.10 oder neuer von https://www.python.org
    echo  Wichtig: Haken bei "Add Python to PATH" setzen!
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% gefunden.
echo.

:: Virtuelle Umgebung erstellen
if exist "venv\Scripts\activate.bat" (
    echo  [OK] Virtuelle Umgebung bereits vorhanden.
) else (
    echo  [INFO] Erstelle virtuelle Umgebung ...
    python -m venv venv
    if errorlevel 1 (
        echo  [FEHLER] Virtuelle Umgebung konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo  [OK] Virtuelle Umgebung erstellt.
)
echo.

:: Umgebung aktivieren
call "venv\Scripts\activate.bat"

:: pip aktualisieren
echo  [INFO] Aktualisiere pip ...
python -m pip install --upgrade pip --quiet

:: NVIDIA GPU prüfen
echo  [INFO] Prüfe GPU ...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Keine NVIDIA GPU gefunden — installiere CPU-Version von PyTorch.
    echo         ^(Die App läuft langsamer, funktioniert aber vollständig.^)
    echo.
    pip install torch==2.5.0 torchaudio==2.5.0 --index-url https://download.pytorch.org/whl/cpu --quiet
) else (
    echo  [OK] NVIDIA GPU gefunden — installiere CUDA-Version von PyTorch.
    echo.
    pip install torch==2.5.0 torchaudio==2.5.0 --index-url https://download.pytorch.org/whl/cu121 --quiet
)

if errorlevel 1 (
    echo  [FEHLER] PyTorch konnte nicht installiert werden.
    pause
    exit /b 1
)
echo  [OK] PyTorch installiert.
echo.

:: Übrige Abhängigkeiten installieren
echo  [INFO] Installiere weitere Abhängigkeiten ...
pip install TTS numpy mss easyocr keyboard customtkinter sounddevice soundfile pydub transformers==4.39.3 deep-translator langdetect --quiet

if errorlevel 1 (
    echo  [FEHLER] Abhängigkeiten konnten nicht vollständig installiert werden.
    pause
    exit /b 1
)
echo  [OK] Alle Abhängigkeiten installiert.
echo.

echo  ╔══════════════════════════════════════════════════╗
echo  ║   Installation abgeschlossen!                    ║
echo  ║                                                   ║
echo  ║   Starte die App mit: start.bat                  ║
echo  ║   Beim ersten Start werden KI-Modelle            ║
echo  ║   heruntergeladen (~2 GB). Einmalig.             ║
echo  ╚══════════════════════════════════════════════════╝
echo.
pause
