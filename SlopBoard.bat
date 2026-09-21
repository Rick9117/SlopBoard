@echo off
REM ===================================================================
REM  Double-click to start SlopBoard (dashboard + tracker).
REM
REM  First run: if the self-contained files aren't here yet, it offers
REM  to set them up (downloads Python + the libraries it needs). After
REM  that it just launches. No coding or terminal required.
REM ===================================================================
cd /d "%~dp0"

set "RUNTIME=dist\SlopBoard\runtime\pythonw.exe"
set "RELEASES=https://github.com/Rick9117/SlopBoard/releases"

REM --- Already set up: launch and quit. --------------------------------
if exist "%RUNTIME%" (
    start "" "%RUNTIME%" launcher.pyw
    exit /b
)

REM --- Not set up. Find a Python to build the runtime with. ------------
set "PYTHON="
py -3 --version >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (
    python --version >nul 2>&1 && set "PYTHON=python"
)

REM --- No Python at all: point to the ready-to-run download. -----------
if not defined PYTHON (
    echo.
    echo   SlopBoard isn't set up yet, and no Python was found to set it up with.
    echo   The easiest option is the ready-to-run version - nothing to install:
    echo.
    echo       %RELEASES%
    echo.
    echo   Opening that page now...
    start "" "%RELEASES%"
    pause
    exit /b
)

REM --- Have Python: offer to build the self-contained runtime. ---------
echo.
echo   SlopBoard needs to install some files the first time it runs.
echo   This downloads Python and the libraries it uses (a few hundred MB)
echo   and can take a few minutes.
echo.
choice /c YN /m "Install now"
if errorlevel 2 exit /b

echo.
echo   Installing, please wait...
%PYTHON% build.py
if errorlevel 1 (
    echo.
    echo   Setup didn't finish - see the messages above.
    pause
    exit /b
)

echo.
echo   Done. Starting SlopBoard...
start "" "%RUNTIME%" launcher.pyw
exit /b
