@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
  pause
  exit /b
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py
  pause
  exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
  python app.py
  pause
  exit /b
)
echo Bitte zuerst Python 3.10 oder neuer von https://www.python.org/downloads/windows/ installieren.
echo Bei der Installation "Add Python to PATH" aktivieren.
pause
