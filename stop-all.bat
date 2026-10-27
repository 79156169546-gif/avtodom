@echo off
setlocal
rem === ⠭ API (8000)  ਭ (5173) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 8000
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 5173
echo [store] Stopped.
echo.
pause
endlocal
