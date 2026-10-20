@echo off
setlocal
rem === Освобождаем порт 8000 (если занят) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 8000

cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo [autodom] Creating virtual environment...
    uv venv .venv --python 3.12
    if errorlevel 1 goto :fail
    echo [autodom] Installing dependencies...
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    if errorlevel 1 goto :fail
)

echo [autodom] API starting on http://127.0.0.1:8000
echo [autodom] API docs: http://127.0.0.1:8000/docs
echo.
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --app-dir ..
goto :end

:fail
echo [autodom] Failed to prepare environment. Need uv and Python 3.12+.

:end
echo.
pause
endlocal
