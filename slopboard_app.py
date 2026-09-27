"""
SlopBoard.exe entry point.

A tiny launcher that gets compiled to SlopBoard.exe (by build.py, via
PyInstaller) so people can start SlopBoard by double-clicking a real program
with an icon instead of a .bat. It does nothing but hand off to the bundled
runtime, which runs the actual app - so PyInstaller only has to package these
few lines, not Streamlit.
"""

import subprocess
import sys
from pathlib import Path

# The folder the program lives in (next to runtime/, launcher.pyw, core/, ...).
# When frozen into an .exe, sys.executable is the .exe; otherwise it's this file.
if getattr(sys, "frozen", False):
    root = Path(sys.executable).resolve().parent
else:
    root = Path(__file__).resolve().parent

# Prefer the bundled, windowless Python; fall back to one on PATH just in case.
pythonw = root / "runtime" / "pythonw.exe"
if not pythonw.exists():
    pythonw = Path("pythonw.exe")

# Start SlopBoard (tracker + dashboard) in the background, then exit.
subprocess.Popen([str(pythonw), str(root / "launcher.pyw")], cwd=str(root))
