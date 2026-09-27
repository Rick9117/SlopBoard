@echo off
REM Run SlopBoard from the source folder.
REM Prefers the self-contained runtime built by "py build.py" (dist\SlopBoard\
REM runtime), so it won't use or clutter your system Python; falls back to your
REM system Python if you haven't built it.
REM For everyday use, open the installed SlopBoard from the Start menu instead.
cd /d "%~dp0"

set "BUNDLED=dist\SlopBoard\runtime\pythonw.exe"
if exist "%BUNDLED%" (
    start "" "%BUNDLED%" launcher.pyw
) else (
    start "" pythonw launcher.pyw
)
