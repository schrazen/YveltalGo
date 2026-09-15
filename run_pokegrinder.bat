@echo off
setlocal

set "ROOT=%~dp0PokeGrinder"
if not exist "%ROOT%\run_pokegrinder.bat" (
  echo Could not find launcher:
  echo %ROOT%\run_pokegrinder.bat
  pause
  exit /b 1
)

if /I "%~1"=="web" (
  call "%ROOT%\run_pokegrinder.bat" web
  exit /b %errorlevel%
)

if /I "%~1"=="browser" (
  call "%ROOT%\run_pokegrinder.bat" web
  exit /b %errorlevel%
)

if /I "%~1"=="desktop" (
  call "%ROOT%\run_pokegrinder.bat" desktop
  exit /b %errorlevel%
)

if /I "%~1"=="desktop-debug" (
  call "%ROOT%\run_pokegrinder.bat" desktop-debug
  exit /b %errorlevel%
)

if /I "%~1"=="desktop-dev-debug" (
  call "%ROOT%\run_pokegrinder.bat" desktop-dev-debug
  exit /b %errorlevel%
)

if /I "%~1"=="electron" (
  call "%ROOT%\run_pokegrinder.bat" desktop
  exit /b %errorlevel%
)

call "%ROOT%\run_pokegrinder.bat" desktop
