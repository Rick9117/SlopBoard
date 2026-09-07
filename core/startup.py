"""
Manage whether the desktop tracker starts automatically when Windows boots.

We do this with a shortcut in the user's Startup folder (the simplest, most
transparent method - the user can also see and delete it themselves). No
registry editing, nothing hidden.

All functions are safe to call on any OS; on non-Windows they simply report
"not enabled" and do nothing, so the rest of the app still runs.
"""

import os
import sys
from pathlib import Path

from core.procname import named_interpreter

ROOT: Path = Path(__file__).resolve().parent.parent

# Name of the shortcut we create in the Startup folder.
SHORTCUT_NAME: str = "SlopBoard Tracker.lnk"


def _startup_dir() -> Path | None:
    """Return the current user's Startup folder on Windows, or None elsewhere."""
    if os.name != "nt":
        return None
    return (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows"
            / "Start Menu" / "Programs" / "Startup")


def _shortcut_path() -> Path | None:
    """Return the full path to our Startup shortcut, or None on non-Windows."""
    folder = _startup_dir()
    return folder / SHORTCUT_NAME if folder else None


def is_enabled() -> bool:
    """Return True if the Startup shortcut exists."""
    path = _shortcut_path()
    return bool(path and path.exists())


def enable() -> bool:
    """Create a Startup shortcut that launches the tracker with no window.

    Returns True on success. Uses pywin32, which is a dependency on Windows.
    """
    path = _shortcut_path()
    if path is None:
        return False
    try:
        import pythoncom
        from win32com.client import Dispatch

        exe = Path(sys.executable)
        windowless = exe.with_name("pythonw.exe")
        base = str(windowless if windowless.exists() else exe)
        # Use a copy named so Task Manager shows "SlopBoard tracker" not pythonw.
        target = named_interpreter(base, "SlopBoard tracker")
        script = str(ROOT / "tracker" / "app_tracker.py")

        shell = Dispatch("WScript.Shell", pythoncom.CoInitialize() or None)
        shortcut = shell.CreateShortcut(str(path))
        shortcut.TargetPath = target
        shortcut.Arguments = f'"{script}"'
        shortcut.WorkingDirectory = str(ROOT)
        shortcut.WindowStyle = 7          # 7 = minimised, no window
        shortcut.Description = "SlopBoard desktop activity tracker"
        shortcut.save()
        return True
    except Exception:
        return False


def disable() -> bool:
    """Remove the Startup shortcut. Returns True if it's gone afterwards."""
    path = _shortcut_path()
    if path is None:
        return False
    try:
        path.unlink(missing_ok=True)
        return True
    except Exception:
        return False
