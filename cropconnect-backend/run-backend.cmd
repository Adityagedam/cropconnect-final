@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Python was not found at %PYTHON_EXE%.
  echo Run from the repo root:
  echo   uv venv --python 3.12 cropconnect-backend\.venv
  echo   uv pip install -r cropconnect-backend\requirements.txt --python cropconnect-backend\.venv\Scripts\python.exe
  exit /b 1
)

"%PYTHON_EXE%" migrate_db.py || exit /b 1
"%PYTHON_EXE%" esp32_ingest.py
