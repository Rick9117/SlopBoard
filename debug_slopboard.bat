@echo off
REM ── DEBUG launcher: runs visibly and logs everything ──
REM Use this instead of run_slopboard.bat to see what's going wrong.
cd /d "%~dp0"
echo Running SlopBoard in debug mode...
echo.

REM 1. Show which Python is being used
echo === Python being used ===
py -c "import sys; print(sys.executable)"
echo.

REM 2. Try to start the Streamlit server DIRECTLY and visibly (not hidden),
REM    so any crash or error message is printed right here.
echo === Starting Streamlit directly (watch for errors below) ===
py -m streamlit run slopboard.py --server.port 8501 --server.headless true

echo.
echo === Streamlit has exited. If you saw errors above, that's the cause. ===
pause
