@echo off
setlocal
rem === ᢮  8000 (᫨ ) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 8000

cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo [store] Creating virtual environment...
    uv venv .venv --python 3.12
    if errorlevel 1 goto :fail
    echo [store] Installing dependencies...
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    if errorlevel 1 goto :fail
)

echo [store] API starting on http://127.0.0.1:8000
echo [store] API docs: http://127.0.0.1:8000/docs
echo.
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --app-dir ..
goto :end

:fail
echo [store] Failed to prepare environment. Need uv and Python 3.12+.

:end
echo.
pause
endlocal
