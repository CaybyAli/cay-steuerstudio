@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" maintenance.py import
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    python maintenance.py import
  ) else (
    py -3 maintenance.py import
  )
)
pause
