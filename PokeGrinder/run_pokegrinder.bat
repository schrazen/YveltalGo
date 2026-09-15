@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%ROOT%\..\.venv\Scripts\python.exe"
set "NPM=C:\Program Files\nodejs\npm.cmd"
set "UI_URL=http://127.0.0.1:5173"

if not exist "%NPM%" (
  echo npm.cmd not found at default path, using PATH lookup...
  set "NPM=npm"
)

if /I "%~1"=="web" goto web
if /I "%~1"=="browser" goto web
if /I "%~1"=="desktop" goto desktop
if /I "%~1"=="electron" goto desktop
if /I "%~1"=="desktop-debug" goto desktop_debug
if /I "%~1"=="desktop-dev-debug" goto desktop_dev_debug

goto desktop

:desktop
echo Starting YveltalGo desktop app mode (single window, no Vite console)...
echo.
echo This will run in background: npm run desktop:app
echo You should only see the Electron app window.
echo.
echo Use "run_pokegrinder.bat desktop-debug" for visible app-mode logs.
echo Use "run_pokegrinder.bat desktop-dev-debug" for Vite dev logs.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$npm='%NPM%'; $wd='%ROOT%\ui\react-app'; Start-Process -FilePath $npm -ArgumentList 'run','desktop:app' -WorkingDirectory $wd -WindowStyle Hidden"
if errorlevel 1 (
  echo Failed to launch hidden desktop process.
  pause
  exit /b 1
)
echo Desktop process started.
exit /b 0

:desktop_debug
echo Starting YveltalGo desktop app mode (visible logs)...
echo.
echo This will run: npm run desktop:app
echo Close the spawned windows to stop services.
echo.
cd /d "%ROOT%\ui\react-app"
call "%NPM%" run desktop:app
exit /b %errorlevel%

:desktop_dev_debug
echo Starting YveltalGo desktop dev mode (Vite + Electron logs)...
echo.
echo This will run: npm run desktop:dev
echo Close the spawned windows to stop services.
echo.
cd /d "%ROOT%\ui\react-app"
call "%NPM%" run desktop:dev
exit /b %errorlevel%

:web

if not exist "%PY%" (
  echo Python venv not found:
  echo %PY%
  pause
  exit /b 1
)

echo Starting backend...
start "" /b cmd /c "cd /d "%ROOT%" && "%PY%" main.py"

echo Starting React UI...
start "" /b cmd /c "cd /d "%ROOT%\ui\react-app" && call "%NPM%" run dev"

echo Waiting for UI server on %UI_URL% ...
for /l %%i in (1,1,60) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing '%UI_URL%' -TimeoutSec 1 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto openui
  timeout /t 1 /nobreak >nul
)

echo UI did not start within 60 seconds.
echo Check the logs in this window for errors.
pause
exit /b 1

:openui
echo UI is up. Opening browser...
start "" "%UI_URL%"
echo Done. Backend and UI are running in this window.
echo Press Ctrl+C to stop both processes.
pause >nul
