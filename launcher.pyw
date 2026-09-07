"""
SlopBoard launcher.

Starts the tracker and dashboard in the background, then opens the dashboard in
an app-style window. When the window is closed, the dashboard server is stopped
but the tracker keeps running.

This launcher is careful about the server: it checks that the port actually
*responds* (not just that something is bound to it), and clears out any stale
SlopBoard server before starting a fresh one. That avoids the "localhost refused
the connection" problem caused by a half-dead server holding the port.

Launched by run_slopboard.bat, which calls it with pythonw so no console appears.
"""

import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

# --- Settings ---
ROOT: Path = Path(__file__).resolve().parent
PORT: int = 8501
# Use 127.0.0.1 (not "localhost") so it matches the server's loopback bind
# exactly and avoids a slow IPv6 (::1) fallback on Windows.
URL: str = f"http://127.0.0.1:{PORT}"

# On Windows this flag hides a child process's console window.
NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# The tracker's single-instance lock port (must match LOCK_PORT in the tracker).
TRACKER_LOCK_PORT: int = 50505

# Show the server and tracker as "SlopBoard" / "SlopBoard tracker" in Task
# Manager. If this ever causes trouble, set it to False to launch plain Python.
FRIENDLY_TASK_MANAGER_NAMES: bool = True

sys.path.insert(0, str(ROOT))            # so "from core import ..." works here
from core.procname import named_interpreter


def python_exe() -> str:
    """Return the console Python (python.exe), which has real stdout/stderr.

    Streamlit misbehaves under pythonw.exe (its stdout/stderr are None), which is
    why the dashboard used to start only after the visible debug script ran. We
    launch the server and tracker with python.exe instead and hide their console
    with CREATE_NO_WINDOW, so they run reliably but invisibly.
    """
    exe = Path(sys.executable)
    console = exe.with_name("python.exe")
    return str(console if console.exists() else exe)


def _log_handle(filename: str) -> TextIO:
    """Open a log file in data/ to capture a background process's output."""
    log_dir = ROOT / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    return open(log_dir / filename, "w", encoding="utf-8")


def server_responds() -> bool:
    """Return True only if the dashboard actually answers an HTTP request.

    This is stronger than checking whether the port is open: a half-dead process
    can hold the port without serving anything, and that is exactly what causes
    'connection refused' in the browser.
    """
    try:
        with urllib.request.urlopen(URL, timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False


def port_is_bound() -> bool:
    """Return True if something is holding the port (responding or not)."""
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def kill_stale_servers() -> None:
    """Stop any leftover SlopBoard dashboard server from a previous run.

    A stale server keeps running OLD code and holds the port, which stops a
    fresh one from starting. We deliberately DON'T touch the tracker: it is a
    singleton (see the lock) and may have been started at boot by auto-start, so
    we never want to kill and race it. Needs psutil; skips quietly if missing.
    """
    try:
        import psutil
    except ImportError:
        return

    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "streamlit" in cmdline and "slopboard.py" in cmdline:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def tracker_running() -> bool:
    """Return True if the tracker is already running (holds its lock port)."""
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", TRACKER_LOCK_PORT))
        return False              # we could bind it, so no tracker is running
    except OSError:
        return True               # port taken -> a tracker already has the lock
    finally:
        probe.close()


def find_browser() -> str | None:
    """Return the path to Chrome or Edge for app-mode, or None if neither exists."""
    options = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in options:
        if Path(path).exists():
            return path
    return None


def start_tracker(python: str) -> None:
    """Start the desktop tracker in the background (hidden, output logged)."""
    subprocess.Popen(
        [python, str(ROOT / "tracker" / "app_tracker.py")],
        cwd=str(ROOT), creationflags=NO_WINDOW,
        stdout=_log_handle("tracker.log"), stderr=subprocess.STDOUT,
    )


def start_dashboard(python: str) -> subprocess.Popen:
    """Start the Streamlit server in the background (hidden, output logged)."""
    return subprocess.Popen(
        [python, "-m", "streamlit", "run", "slopboard.py",
         "--server.port", str(PORT),
         # Listen on loopback only: no Windows Firewall prompt, no exposing the
         # dashboard on the network, and no cross-origin request to be rejected.
         "--server.address", "127.0.0.1",
         "--server.headless", "true",
         # This is a local, single-user dashboard, so the cross-site (CORS/XSRF)
         # checks add nothing but were causing the browser's "access denied".
         "--server.enableCORS", "false",
         "--server.enableXsrfProtection", "false",
         "--browser.gatherUsageStats", "false"],
        cwd=str(ROOT), creationflags=NO_WINDOW,
        stdout=_log_handle("dashboard.log"), stderr=subprocess.STDOUT,
    )


def _wait_until(condition: Callable[[], bool], timeout: int) -> None:
    """Wait until condition() is True, or the timeout (seconds) is reached."""
    for _ in range(timeout * 2):        # check twice a second
        if condition():
            return
        time.sleep(0.5)


def open_window(server: subprocess.Popen | None) -> None:
    """Open the dashboard in an app window, then stop the server when it closes.

    We open the window in a private browser profile on purpose. A plain
    "chrome --app=URL" hands the request to an already-running Chrome and the
    process we launched exits instantly - which used to make us terminate the
    server the moment the window appeared (the "connection refused" you saw). A
    separate --user-data-dir forces our own window that lives until you close it.

    As a safety net, if the launched process still returns almost immediately
    (it handed off anyway), we keep the server running instead of killing it.
    """
    browser = find_browser()
    if browser is None:
        webbrowser.open(URL)
        if server is not None:
            server.wait()                # keep the launcher (and server) alive
        return

    time.sleep(1.0)                      # let the server settle before first load
    profile = ROOT / "data" / ".browser-profile"

    started = time.monotonic()
    window = subprocess.Popen(
        [browser, f"--app={URL}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check",
         "--window-size=1240,840"]
    )
    window.wait()                        # blocks until the app window is closed

    # If that returned in a blink, the browser handed off to an existing window,
    # so the dashboard is still on screen - leave the server up. Otherwise the
    # user really closed the window, so stop the server (the tracker keeps going).
    if time.monotonic() - started < 3 and server is not None:
        server.wait()
    elif server is not None:
        server.terminate()


def main() -> None:
    """Start everything and open the dashboard window.

    Any unexpected error is written to data/launcher.log so problems are
    visible even though this runs without a console window.
    """
    try:
        python = python_exe()
        # Renamed copies so Task Manager shows friendly names (see procname).
        if FRIENDLY_TASK_MANAGER_NAMES:
            windowless = Path(python).with_name("pythonw.exe")
            tracker_base = str(windowless) if windowless.exists() else python
            server_python = named_interpreter(python, "SlopBoard")
            tracker_python = named_interpreter(tracker_base, "SlopBoard tracker")
        else:
            server_python = tracker_python = python

        # Clear out only a stale SERVER (fresh code + free port). The tracker is
        # left alone; we start one only if none is already running.
        kill_stale_servers()
        _wait_until(lambda: not port_is_bound(), timeout=5)

        if not tracker_running():
            start_tracker(tracker_python)     # exactly one tracker, ever
        server = start_dashboard(server_python)
        _wait_until(server_responds, timeout=30)

        if server_responds():
            open_window(server)
        else:
            # The server never came up. Open the URL anyway so the user sees
            # the browser's error rather than nothing happening.
            webbrowser.open(URL)
    except Exception as error:
        log = ROOT / "data" / "launcher.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        import traceback
        log.write_text(f"Launcher failed:\n{traceback.format_exc()}",
                       encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
