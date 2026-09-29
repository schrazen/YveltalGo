@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
set "NPM=C:\Program Files\nodejs\npm.cmd"
set "UI_DIR=%ROOT%\ui\react-app"
set "UI_URL=http://127.0.0.1:5173"

:: Verify Node / NPM
if not exist "%NPM%" (
  set "NPM=npm"
)

:: Handle command-line arguments directly
if /I "%~1"=="desktop" goto desktop
if /I "%~1"=="electron" goto desktop
if /I "%~1"=="debug" goto desktop_debug
if /I "%~1"=="desktop-debug" goto desktop_debug
if /I "%~1"=="web" goto web
if /I "%~1"=="browser" goto web
if /I "%~1"=="rebuild" goto rebuild
if /I "%~1"=="clean" goto cleanup
if /I "%~1"=="kill" goto cleanup
if /I "%~1"=="stop" goto cleanup

:menu
cls
echo ===================================================================
echo                        YveltalGo Suite
echo ===================================================================
echo   [1] Desktop App Mode   (Fast Native Window - Recommended)
echo   [2] Desktop Debug Mode (Visible Console with Live Logs)
echo   [3] Web Browser Mode   (React Dev Server + Flask on 8787)
echo   [4] Rebuild Frontend   (Vite Recompile ^& Launch Desktop)
echo   [5] Clean Stale Procs  (Kill Port 8787 ^& Orphaned Electrons)
echo   [6] Exit
echo ===================================================================
choice /C 123456 /N /T 8 /D 1 /M "Select option [1-6] (Auto-starts [1] in 8s): "

if errorlevel 6 exit /b 0
if errorlevel 5 goto cleanup
if errorlevel 4 goto rebuild
if errorlevel 3 goto web
if errorlevel 2 goto desktop_debug
if errorlevel 1 goto desktop

:: -------------------------------------------------------------
:: Pre-flight Environment Checks
:: -------------------------------------------------------------
:preflight
if not exist "%PY%" (
  echo.
  echo [ERROR] Python virtual environment was not found at:
  echo   %PY%
  echo.
  echo Run the following in your terminal to set it up:
  echo   python -m venv .venv
  echo   .\.venv\Scripts\pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

if not exist "%ROOT%\config.json" (
  if exist "%ROOT%\config.example.json" (
    echo [Setup] Creating initial config.json from template...
    copy /Y "%ROOT%\config.example.json" "%ROOT%\config.json" >nul
    echo [Setup] Created config.json. Please add your token before grinding!
  )
)

if not exist "%UI_DIR%\node_modules" (
  echo [Setup] Installing UI dependencies (first run only)...
  cd /d "%UI_DIR%"
  call "%NPM%" install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
)

if not exist "%UI_DIR%\dist\index.html" (
  echo [Setup] Building dashboard UI (first run only)...
  cd /d "%UI_DIR%"
  call "%NPM%" run build
  if errorlevel 1 (
    echo [ERROR] UI build failed.
    pause
    exit /b 1
  )
)
exit /b 0

:: -------------------------------------------------------------
:: Mode: Fast Desktop App
:: -------------------------------------------------------------
:desktop
call :preflight
if errorlevel 1 exit /b 1

echo Starting YveltalGo Desktop App...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$npm='%NPM%'; $wd='%UI_DIR%'; Start-Process -FilePath $npm -ArgumentList 'run','desktop:app' -WorkingDirectory $wd -WindowStyle Hidden"
if errorlevel 1 (
  echo [ERROR] Failed to start desktop process. Try option [2] Desktop Debug Mode.
  pause
  exit /b 1
)
echo Window launched.
exit /b 0

:: -------------------------------------------------------------
:: Mode: Desktop Debug (Visible Console)
:: -------------------------------------------------------------
:desktop_debug
call :preflight
if errorlevel 1 exit /b 1

echo Starting YveltalGo Desktop App (Debug Mode with Live Logs)...
echo Close this window or the Electron app to stop.
echo.
cd /d "%UI_DIR%"
call "%NPM%" run desktop:app
exit /b %errorlevel%

:: -------------------------------------------------------------
:: Mode: Rebuild Frontend & Launch
:: -------------------------------------------------------------
:rebuild
call :preflight
if errorlevel 1 exit /b 1

echo Rebuilding React Frontend...
cd /d "%UI_DIR%"
call "%NPM%" run build
if errorlevel 1 (
  echo [ERROR] Build failed!
  pause
  exit /b 1
)
goto desktop

:: -------------------------------------------------------------
:: Mode: Web Browser
:: -------------------------------------------------------------
:web
call :preflight
if errorlevel 1 exit /b 1

echo Starting Flask backend...
start "YveltalGo Backend" /b cmd /c "cd /d "%ROOT%" && "%PY%" main.py"

echo Starting React UI Dev Server...
start "YveltalGo Vite Dev" /b cmd /c "cd /d "%UI_DIR%" && call "%NPM%" run dev"

echo Waiting for UI server on %UI_URL% ...
for /l %%i in (1,1,45) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing '%UI_URL%' -TimeoutSec 1 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto openui
  timeout /t 1 /nobreak >nul
)

echo [WARNING] UI dev server taking longer than expected to report ready.
echo Opening browser anyway...

:openui
start "" "%UI_URL%"
echo.
echo ===================================================================
echo Backend and Web UI are running.
echo API:     http://127.0.0.1:8787
echo Web UI:  %UI_URL%
echo Press Ctrl+C in this window to stop.
echo ===================================================================
pause >nul
exit /b 0

:: -------------------------------------------------------------
:: Cleanup: Terminate Stale Instances
:: -------------------------------------------------------------
:cleanup
echo Cleaning up background processes...
taskkill /F /IM electron.exe >nul 2>&1

powershell -NoProfile -Command "$conns = Get-NetTCPConnection -LocalPort 8787 -ErrorAction SilentlyContinue; if ($conns) { $conns | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
echo Cleanup complete.
ping 127.0.0.1 -n 2 >nul
if not "%~1"=="" exit /b 0
goto menu
