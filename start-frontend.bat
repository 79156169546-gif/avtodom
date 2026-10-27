@echo off
setlocal
rem === ᢮  5173 (᫨ ) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-port.ps1" -Port 5173

cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [store] Installing dependencies...
    call npm install
    if errorlevel 1 goto :fail
)

echo [store] Storefront starting on http://127.0.0.1:5173
echo.
call npm run dev
goto :end

:fail
echo [store] Failed to install dependencies. Need Node.js 18+ and npm.

:end
echo.
pause
endlocal
