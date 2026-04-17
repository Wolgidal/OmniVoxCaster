@echo off
title OmniVox Caster - Installation

echo.
echo  ================================================
echo   OmniVox Caster - Voxcaster Imperialis
echo   Installation
echo  ================================================
echo.

:: Python pruefen
python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Python wurde nicht gefunden.
    echo  Bitte installiere Python 3.10 oder neuer:
    echo  https://www.python.org/downloads/
    echo  Wichtig: Haken bei "Add Python to PATH" setzen!
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)

if %PYMAJOR% LSS 3 (
    echo  [FEHLER] Python %PYVER% wird nicht unterstuetzt.
    echo  Bitte installiere Python 3.10 oder 3.11.
    pause
    exit /b 1
)
if %PYMAJOR% EQU 3 if %PYMINOR% LSS 10 (
    echo  [FEHLER] Python %PYVER% ist zu alt.
    echo  Bitte installiere Python 3.10 oder 3.11.
    pause
    exit /b 1
)
if %PYMAJOR% EQU 3 if %PYMINOR% GTR 11 (
    echo  [FEHLER] Python %PYVER% wird nicht unterstuetzt.
    echo  Das KI-Modell (Coqui TTS) benoetigt Python 3.10 oder 3.11.
    echo.
    echo  Bitte installiere Python 3.11:
    echo  https://www.python.org/downloads/release/python-3119/
    echo  Wichtig: Haken bei "Add Python to PATH" setzen!
    pause
    exit /b 1
)

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
echo.

:: Abhaengigkeiten installieren (ohne torch - wird danach separat installiert)
echo  [INFO] Installiere Abhaengigkeiten ...
pip install TTS numpy mss easyocr keyboard customtkinter sounddevice soundfile pydub transformers==4.39.3 deep-translator langdetect --quiet

if errorlevel 1 (
    echo  [FEHLER] Abhaengigkeiten konnten nicht vollstaendig installiert werden.
    pause
    exit /b 1
)
echo  [OK] Abhaengigkeiten installiert.
echo.

:: NVIDIA GPU pruefen und passende torch-Version installieren
:: Wichtig: torch wird NACH allen anderen Paketen installiert, damit es nicht
:: durch TTS-Abhaengigkeiten mit einer CPU-Version ueberschrieben wird.
echo  [INFO] Pruefe GPU und installiere PyTorch ...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    if exist "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe" (
        "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe" >nul 2>&1
    )
)

if errorlevel 1 (
    echo  [INFO] Keine NVIDIA GPU gefunden.
    echo  [INFO] Installiere CPU-Version von PyTorch.
    echo  [INFO] Die App funktioniert, ist aber langsamer.
    echo.
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
) else (
    echo  [OK] NVIDIA GPU gefunden - installiere CUDA-Version.
    echo.
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 --quiet
)

if errorlevel 1 (
    echo  [FEHLER] PyTorch konnte nicht installiert werden.
    pause
    exit /b 1
)
echo  [OK] PyTorch installiert.
echo.

echo  ================================================
echo   Installation abgeschlossen!
echo.
echo   Starte die App mit: start.bat
echo.
echo   Beim ersten Start werden KI-Modelle
echo   heruntergeladen (~2 GB). Nur einmalig.
echo  ================================================
echo.
pause
