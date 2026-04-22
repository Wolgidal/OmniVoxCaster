@echo off
title OmniVox Caster - Installation
cd /d "%~dp0"

:: --------------------------------------------------------
:: Logfile einrichten
:: --------------------------------------------------------
set LOGFILE=%~dp0install.log
echo. > "%LOGFILE%"
echo [%date% %time%] Installation gestartet >> "%LOGFILE%"

:: Alle Ausgaben zusaetzlich ins Logfile schreiben
:: (Fehlermeldungen bleiben im Fenster sichtbar, alles landet im Log)

echo.
echo  ================================================
echo   OmniVox Caster - Voxcaster Imperialis
echo   Installation
echo  ================================================
echo.

set PYTMP=%TEMP%\omv_pycheck.txt

:: --------------------------------------------------------
:: Python 3.10 oder 3.11 suchen
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

winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements >nul 2>&1
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    set PYVER=3.11
    del "%PYTMP%" >nul 2>&1
    echo  [OK] Python 3.11 via winget installiert.
    goto :python_ok
)

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
echo           Bitte manuell installieren: https://www.python.org/downloads/release/python-3119/
echo           Wichtig: Haken bei "Add Python to PATH" setzen!
echo [FEHLER] Python-Installation fehlgeschlagen >> "%LOGFILE%"
exit /b 0
exit /b 1

:python_ok
del "%PYTMP%" >nul 2>&1
echo  [OK] Python %PYVER% gefunden.
echo [OK] Python %PYVER% >> "%LOGFILE%"
echo.

:: --------------------------------------------------------
:: Visual C++ Build Tools pruefen und ggf. installieren
:: (benoetigt fuer Cython-Kompilierung von XTTSv2)
:: --------------------------------------------------------
echo  [INFO] Pruefe Visual C++ Build Tools ...
call :check_vcpp
if /I "%VCPP_OK%"=="1" (
    echo  [OK] Visual C++ Build Tools gefunden.
    echo [OK] VC++ Build Tools vorhanden >> "%LOGFILE%"
) else (
    echo  [INFO] Visual C++ Build Tools nicht gefunden - werden installiert ...
    echo  [INFO] Dies kann einige Minuten dauern ...
    echo [INFO] Installiere VC++ Build Tools >> "%LOGFILE%"
    winget install Microsoft.VisualStudio.2022.BuildTools --silent --accept-package-agreements --accept-source-agreements --override "--quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        echo  [WARN] Automatische Installation fehlgeschlagen.
        echo  [WARN] Falls der naechste Schritt scheitert, installiere manuell:
        echo         https://visualstudio.microsoft.com/visual-cpp-build-tools/
        echo [WARN] VC++ Auto-Install fehlgeschlagen >> "%LOGFILE%"
    ) else (
        echo  [OK] Visual C++ Build Tools installiert.
        echo [OK] VC++ Build Tools installiert >> "%LOGFILE%"
    )
)
echo.

:: --------------------------------------------------------
:: Virtuelle Umgebung erstellen
:: --------------------------------------------------------
if exist "venv\Scripts\python.exe" (
    echo  [OK] Virtuelle Umgebung bereits vorhanden.
) else (
    echo  [INFO] Erstelle virtuelle Umgebung ...
    %PYTHON_EXE% -m venv venv >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        echo  [FEHLER] Virtuelle Umgebung konnte nicht erstellt werden.
        echo  [FEHLER] Details in install.log
        echo [FEHLER] venv-Erstellung fehlgeschlagen >> "%LOGFILE%"
        pause
        exit /b 1
    )
    echo  [OK] Virtuelle Umgebung erstellt.
)
echo.

:: --------------------------------------------------------
:: pip auf kompatible Version setzen
:: pip 24+ hat striktere Metadaten-Validierung die TTS 0.22.0 nicht besteht
:: --------------------------------------------------------
echo  [INFO] Aktualisiere pip ...
venv\Scripts\python.exe -m pip install "pip>=23,<24" --quiet >> "%LOGFILE%" 2>&1
echo.

:: --------------------------------------------------------
:: Build-Umgebung (Cython + wheel)
:: --------------------------------------------------------
echo  [INFO] Bereite Build-Umgebung vor ...
venv\Scripts\pip.exe install wheel Cython >> "%LOGFILE%" 2>&1

venv\Scripts\python.exe -c "import Cython" >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Cython konnte nicht installiert werden. Details in install.log
    echo [FEHLER] Cython-Install fehlgeschlagen >> "%LOGFILE%"
    pause
    exit /b 1
)
echo  [OK] Build-Umgebung bereit.
echo.

:: --------------------------------------------------------
:: Abhaengigkeiten installieren
:: --------------------------------------------------------
echo  [INFO] Installiere Abhaengigkeiten ...
venv\Scripts\pip.exe install numpy==1.26.4 pandas==1.5.3 mss easyocr keyboard customtkinter sounddevice soundfile pydub transformers==4.39.3 deep-translator langdetect >> "%LOGFILE%" 2>&1

if errorlevel 1 (
    echo  [FEHLER] Abhaengigkeiten konnten nicht installiert werden. Details in install.log
    echo [FEHLER] Abhaengigkeiten-Install fehlgeschlagen >> "%LOGFILE%"
    pause
    exit /b 1
)
echo  [OK] Abhaengigkeiten installiert.
echo.

echo  [INFO] Installiere TTS (Coqui XTTSv2) ...
set PYTHONPATH=%~dp0venv\Lib\site-packages
venv\Scripts\pip.exe install TTS==0.22.0 --no-build-isolation >> "%LOGFILE%" 2>&1
set PYTHONPATH=
if errorlevel 1 (
    echo  [FEHLER] TTS konnte nicht installiert werden. Details in install.log
    echo [FEHLER] TTS-Install fehlgeschlagen >> "%LOGFILE%"
    pause
    exit /b 1
)
echo  [OK] TTS installiert.
echo.

:: --------------------------------------------------------
:: PyTorch installieren - NACH allen anderen Paketen
:: --------------------------------------------------------
echo  [INFO] Pruefe GPU und installiere PyTorch ...
set GPU_BACKEND=cpu

call :detect_nvidia_gpu

if /I "%GPU_BACKEND%"=="cuda" (
    echo  [OK] NVIDIA GPU gefunden - installiere CUDA-Version.
    echo [INFO] PyTorch CUDA >> "%LOGFILE%"
    echo.
    venv\Scripts\pip.exe uninstall -y torch torchaudio torchvision >nul 2>&1
    venv\Scripts\pip.exe install --upgrade --force-reinstall torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu128 >> "%LOGFILE%" 2>&1
) else (
    echo  [INFO] Keine NVIDIA GPU gefunden - installiere CPU-Version.
    echo  [INFO] Die App funktioniert, ist aber langsamer.
    echo [INFO] PyTorch CPU >> "%LOGFILE%"
    echo.
    venv\Scripts\pip.exe uninstall -y torch torchaudio torchvision >nul 2>&1
    venv\Scripts\pip.exe install --upgrade --force-reinstall torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu >> "%LOGFILE%" 2>&1
)

if errorlevel 1 (
    echo  [FEHLER] PyTorch konnte nicht installiert werden. Details in install.log
    echo [FEHLER] PyTorch-Install fehlgeschlagen >> "%LOGFILE%"
    pause
    exit /b 1
)
echo  [OK] PyTorch installiert.
venv\Scripts\python.exe -c "import torch; print('[INFO] Torch-Version:', torch.__version__); print('[INFO] Torch-CUDA-Build:', torch.version.cuda or 'cpu-only'); print('[INFO] CUDA verfuegbar:', torch.cuda.is_available())"
echo.

:: --------------------------------------------------------
:: NumPy/Pandas NACH PyTorch fixieren
:: PyTorch ueberschreibt numpy auf 2.x - pandas 1.5.3 benoetigt aber 1.x
:: --------------------------------------------------------
echo  [INFO] Fixiere NumPy/Pandas nach PyTorch-Installation ...
venv\Scripts\pip.exe install --upgrade --force-reinstall numpy==1.26.4 pandas==1.5.3 --quiet >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo  [FEHLER] NumPy/Pandas konnten nicht gesetzt werden. Details in install.log
    echo [FEHLER] NumPy/Pandas-Fix fehlgeschlagen >> "%LOGFILE%"
    pause
    exit /b 1
)
echo  [OK] NumPy 1.26.4 und Pandas 1.5.3 wiederhergestellt.
echo.

echo [%date% %time%] Installation erfolgreich abgeschlossen >> "%LOGFILE%"

echo  ================================================
echo   Installation abgeschlossen!
echo.
echo   Starte die App mit: start.bat
echo.
echo   Beim ersten Start werden KI-Modelle
echo   heruntergeladen (~2 GB). Nur einmalig.
echo.
echo   Protokoll: install.log
echo  ================================================
echo.
exit /b 0
goto :eof

:: --------------------------------------------------------
:: Visual C++ Build Tools pruefen
:: --------------------------------------------------------
:check_vcpp
set VCPP_OK=0

:: Pruefe auf cl.exe (MSVC Compiler) im Standard-Installationspfad
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC" ( set VCPP_OK=1 & goto :eof )
if exist "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC"      ( set VCPP_OK=1 & goto :eof )
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC" ( set VCPP_OK=1 & goto :eof )

:: Pruefe ob cl.exe im PATH erreichbar ist (z.B. Visual Studio vollstaendig installiert)
where cl.exe >nul 2>&1
if not errorlevel 1 ( set VCPP_OK=1 & goto :eof )

:: Pruefe auf installierte VS-Versionen via Registry
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\SxS\VS7" >nul 2>&1
if not errorlevel 1 ( set VCPP_OK=1 & goto :eof )

goto :eof

:: --------------------------------------------------------
:: NVIDIA GPU erkennen
:: --------------------------------------------------------
:detect_nvidia_gpu
nvidia-smi >nul 2>&1
if not errorlevel 1 ( set GPU_BACKEND=cuda & goto :eof )

if exist "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe" (
    "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe" >nul 2>&1
    if not errorlevel 1 ( set GPU_BACKEND=cuda & goto :eof )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$gpus = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }; if ($gpus) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 ( set GPU_BACKEND=cuda )
goto :eof
