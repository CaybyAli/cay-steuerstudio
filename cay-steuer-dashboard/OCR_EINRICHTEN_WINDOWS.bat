@echo off
setlocal
cd /d "%~dp0"
echo Cay Steuerstudio - lokale OCR fuer gescannte Kontoauszuege
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst EINRICHTEN_WINDOWS.bat ausfuehren.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import intake; raise SystemExit(0 if intake.tesseract_path() else 1)"
if not errorlevel 1 goto done
where winget >nul 2>nul
if errorlevel 1 goto manual
echo Installiert Tesseract lokal ueber Windows-Paketverwaltung.
echo Eine Windows-Abfrage des Installers ist gegebenenfalls zu bestaetigen.
winget install --exact --id UB-Mannheim.TesseractOCR
if errorlevel 1 goto manual
".venv\Scripts\python.exe" -c "import intake; raise SystemExit(0 if intake.tesseract_path() else 1)"
if errorlevel 1 goto manual
:done
echo OCR-Programm gefunden. Cay Steuerstudio neu starten.
echo Wenn das deutsche Sprachpaket fehlt, wird Englisch genutzt und angezeigt.
echo Vorzeichen und Betraege in gescannten Auszuegen immer am Original pruefen.
pause
exit /b 0
:manual
echo Automatische Installation nicht moeglich.
echo Tesseract fuer Windows nach offizieller Anleitung installieren:
echo https://tesseract-ocr.github.io/tessdoc/Installation.html
echo Danach Cay Steuerstudio neu starten. Bereits hochgeladene Dateien bleiben gespeichert.
pause
exit /b 1
