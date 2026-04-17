@echo off
title OmniVox Caster - Installation
cd /d "%~dp0"

echo.
echo  ================================================
echo   OmniVox Caster - Voxcaster Imperialis
echo   Installation
echo  ================================================
echo.

set PYTMP=%TEMP%\omv_pycheck.txt

:: --------------------------------------------------------
:: Python 3.10 oder 3.11 suchen
:: Ausgabe in Temp-Datei, um Pipe/Sonderzeichen-Probleme zu vermeiden
:: --------------------------------------------------------
set PYTHON_EXE=
set PYVER=

py -3.11 --version > "%PYTMP%" 2>&1
findstr /C:"Python 3.11" "%PYTMP%" >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=py -3.11 & set PYVER=3.11 & goto :python_ok )

py -3.10 --version > "%PYTMP%" 2>&1
findstr /C:"Python 3.10" "%PYTMP%" >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=py -3.10 & set PYVER=3.10 & goto :python_ok )

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    set PYVER=3.11
    goto :python_ok
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
    set PYVER=3.10
    goto :python_ok
)

python --version > "%PYTMP%" 2>&1
findstr /C:"Python 3.11" "%PYTMP%" >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=python & set PYVER=3.11 & goto :python_ok )
findstr /C:"Python 3.10" "%PYTMP%" >nul 2>&1
if not errorlevel 1 ( set PYTHON_EXE=python & set PYVER=3.10 & goto :python_ok )

for /f "tokens=2 delims= " %%v in (%PYTMP%) do echo  [WARN] Python %%v gefunden - benoetigt wird 3.10 oder 3.11.
del "%PYTMP%" >nul 2>&1

:: --------------------------------------------------------
:: Python 3.11 automatisch installieren
:: --------------------------------------------------------
echo  [INFO] Python 3.11 wird automatisch installiert ...
echo.

:: Versuch 1: py install (neuer Windows Python Launcher)
py install 3.11 >nul 2>&1
py -3.11 --version > "%PYTMP%" 2>&1
findstr /C:"Python 3.11" "%PYTMP%" >nul 2>&1
if not errorlevel 1 (
    set PYTHON_EXE=py -3.11
    set PYVER=3.11
    del "%PYTMP%" >nul 2>&1
    echo  [OK] Python 3.11 via py installer installiert.
    goto :python_ok
)

:: Versuch 2: winget
winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    set PYVER=3.11
    del "%PYTMP%" >nul 2>&1
    echo  [OK] Python 3.11 via winget installiert.
    goto :python_ok
)

:: Versuch 3: Download per PowerShell
echo  [INFO] Lade Python 3.11 Installer herunter ...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python311_setup.exe'" >nul 2>&1
if errorlevel 1 goto :python_failed

echo  [INFO] Installiere Python 3.11 ...
"%TEMP%\python311_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%TEMP%\python311_setup.exe" >nul 2>&1

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    set PYVER=3.11
    del "%PYTMP%" >nul 2>&1
    echo  [OK] Python 3.11 installiert.
    goto :python_ok
)

:python_failed
del "%PYTMP%" >nul 2>&1
echo  [FEHLER] Python 3.11 konnte nicht automatisch installiert werden.
echo.
echo  Bitte manuell installieren und danach install.bat erneut ausfuehren:
echo  https://www.python.org/downloads/release/python-3119/
echo  Wichtig: Haken bei "Add Python to PATH" setzen!
pause
exit /b 1

:python_ok
del "%PYTMP%" >nul 2>&1
echo  [OK] Python %PYVER% gefunden.
echo.

:: --------------------------------------------------------
:: Virtuelle Umgebung erstellen
:: --------------------------------------------------------
if exist "venv\Scripts\python.exe" (
    echo  [OK] Virtuelle Umgebung bereits vorhanden.
) else (
    echo  [INFO] Erstelle virtuelle Umgebung ...
    %PYTHON_EXE% -m venv venv
    if errorlevel 1 (
        echo  [FEHLER] Virtuelle Umgebung konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo  [OK] Virtuelle Umgebung erstellt.
)
echo.

:: --------------------------------------------------------
:: pip aktualisieren (auf Version die mit TTS kompatibel ist)
:: pip 24+ hat striktere Metadaten-Validierung die TTS 0.22.0 nicht besteht
:: --------------------------------------------------------
echo  [INFO] Aktualisiere pip ...
venv\Scripts\python.exe -m pip install "pip>=23,<24" --quiet
echo.

:: --------------------------------------------------------
:: Abhaengigkeiten installieren (torch kommt danach separat)
:: --------------------------------------------------------

:: Build-Umgebung vorbereiten
echo  [INFO] Bereite Build-Umgebung vor ...
venv\Scripts\pip.exe install wheel Cython

:: Cython pruefen
venv\Scripts\python.exe -c "import Cython" >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Cython konnte nicht installiert werden.
    pause
    exit /b 1
)
echo  [OK] Build-Umgebung bereit.
echo.

echo  [INFO] Installiere Abhaengigkeiten ...
venv\Scripts\pip.exe install numpy mss easyocr keyboard customtkinter sounddevice soundfile pydub transformers==4.39.3 deep-translator langdetect --quiet

if errorlevel 1 (
    echo  [FEHLER] Abhaengigkeiten konnten nicht vollstaendig installiert werden.
    pause
    exit /b 1
)
echo  [OK] Abhaengigkeiten installiert.
echo.

echo  [INFO] Installiere TTS (Coqui XTTSv2) ...
set PYTHONPATH=%~dp0venv\Lib\site-packages
venv\Scripts\pip.exe install TTS==0.22.0 --no-build-isolation
set PYTHONPATH=
if errorlevel 1 (
    echo  [FEHLER] TTS konnte nicht installiert werden.
    pause
    exit /b 1
)
echo  [OK] TTS installiert.
echo.

:: --------------------------------------------------------
:: PyTorch installieren - NACH allen anderen Paketen, damit
:: TTS die CUDA-Version nicht mit CPU ueberschreiben kann
:: --------------------------------------------------------
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
    venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
) else (
    echo  [OK] NVIDIA GPU gefunden - installiere CUDA-Version.
    echo.
    venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 --quiet
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
