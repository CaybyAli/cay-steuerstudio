@echo off
setlocal
cd /d "%~dp0"
echo Cay Steuerstudio 0.3.6 - einmalige Einrichtung
echo Erstellt eine lokale Python-Umgebung und installiert PDF-Text- und Bildunterstuetzung.
echo Dafuer wird Internet benoetigt. Ollama-Modelle werden nicht erneut geladen.
if exist ".venv\Scripts\python.exe" goto install
py -3 -c "import sys; raise SystemExit(sys.version_info < (3,10))" >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -c "import sys; raise SystemExit(sys.version_info < (3,10))" >nul 2>nul
  if errorlevel 1 goto missing
  python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" goto missing
:install
".venv\Scripts\python.exe" -m pip install -r requirements-pdf.txt
if errorlevel 1 (
  echo PDF-Unterstuetzung konnte nicht installiert werden. Fehlermeldung bitte aufheben.
  echo Die Grundfunktionen koennen mit START_WINDOWS.bat gestartet werden.
  pause
  exit /b 1
)
echo Fertig. Jetzt START_WINDOWS.bat doppelklicken.
pause
exit /b 0
:missing
echo Python 3.10 oder neuer fehlt oder die Umgebung konnte nicht erstellt werden.
echo Python von https://www.python.org/downloads/windows/ installieren.
echo Dabei Add Python to PATH aktivieren. Danach diese Datei erneut starten.
pause
exit /b 1
