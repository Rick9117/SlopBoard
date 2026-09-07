"""
The desktop app tracker.

Every few seconds it checks which application is in the foreground - your active,
focused window - and adds that time to today's tally. Only the active window is
counted, so an app left running in the background adds no time. Totals are saved
to data/app_activity.csv (columns: date, app, name, seconds), where:
  - app  is the process name  (e.g. "SC2_x64.exe") - stable, used as the key
  - name is the window title   (e.g. "StarCraft II") - the friendly display name

Real tracking is Windows-only (it uses pywin32 + psutil). Run with --simulate on
any operating system to write fake data, which is useful for testing.

    py tracker/app_tracker.py            # real tracking (Windows)
    py tracker/app_tracker.py --simulate # fake data (any OS)
"""

import csv
import socket
import sys
import time
from datetime import date
from pathlib import Path

# --- Settings and file paths ---
DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
APP_CSV: Path = DATA_DIR / "app_activity.csv"
STOP_FLAG: Path = DATA_DIR / "stop.flag"   # the dashboard writes this to ask us to stop

SAMPLE_SECONDS: int = 5      # how often to check the foreground window
FLUSH_EVERY: int = 1         # save to disk every sample, so the dashboard is
                             # at most a few seconds behind what you're doing
LOCK_PORT: int = 50505       # bound as a lock so only one tracker runs at once

# Apps whose window title we don't want to follow. Browsers rename their window
# with every tab, so we pin them to one stable name; without this, Chrome would
# be labelled after whatever window was last focused (e.g. SlopBoard's own tab).
KNOWN_APPS: dict[str, str] = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
}

# SlopBoard's dashboard opens in a browser window with exactly this title. We
# skip it so the dashboard never counts the time you spend looking at itself.
OWN_WINDOW_TITLE: str = "SlopBoard"

# One app's running tally for the day: process name -> (window title, seconds).
DayTotals = dict[str, tuple[str, int]]


def log(message: str) -> None:
    """Print progress, safely, wherever the tracker was started from.

    When auto-started on boot the tracker runs under pythonw.exe, whose stdout
    isn't shown. So we also append to data/tracker.log, which lets you confirm
    the tracker actually started at boot. Never raises - logging is best-effort.
    """
    if sys.stdout is not None:
        # A real stream: the console shows it, or the launcher captures it to
        # data/tracker.log. Either way, don't also write the file ourselves.
        try:
            print(message, flush=True)
            return
        except Exception:
            pass
    # No stdout (auto-started under pythonw): record to the log file instead.
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with (DATA_DIR / "tracker.log").open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except Exception:
        pass


def set_process_name(name: str) -> None:
    """Give this process a friendly name in Task Manager, if setproctitle exists.

    Safe to call either way: if the library is not installed, the process simply
    keeps its default name (pythonw.exe).
    """
    try:
        import setproctitle
        setproctitle.setproctitle(name)
    except Exception:
        pass


def acquire_single_instance() -> socket.socket | None:
    """Make sure only one tracker runs at a time.

    We bind a local port as a lock. If the bind fails, another tracker already
    holds it, so we return None. The lock frees automatically when the process
    ends, so there are no leftover lock files. Keep the returned socket alive.
    """
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
        return lock
    except OSError:
        return None


def clean_title(title: str) -> str:
    """Reduce a busy window title to just the application name.

    Windows titles are usually "document - Section - App Name", where the real
    app name is the last part after the final " - ". For example:
      "Slopper Project - Claude - Google Chrome"  ->  "Google Chrome"
      "README.md - Visual Studio Code"            ->  "Visual Studio Code"
    If there's no separator we keep the whole title.
    """
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return title.strip()


def tracking_supported() -> bool:
    """Return True if we can read the foreground window (Windows + libraries)."""
    try:
        import win32gui, win32process, psutil  # noqa: F401
    except ImportError:
        return False
    return True


def active_app() -> tuple[str, str] | None:
    """Return the foreground app as (process_name, display_name), or None.

    None means we couldn't read the window, or it's SlopBoard's own dashboard
    window (which we deliberately skip). Known apps (browsers) get a fixed
    display name; every other app uses its cleaned-up window title. For example:
    ("SC2_x64.exe", "StarCraft II") or ("chrome.exe", "Google Chrome").
    """
    try:
        import win32gui
        import win32process
        import psutil
    except ImportError:
        return None

    try:
        window = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(window)
        if pid <= 0:
            return None

        proc = psutil.Process(pid)
        process_name = proc.name()                          # "SC2_x64.exe"
        raw_title = win32gui.GetWindowText(window).strip()  # full window title

        # Don't track ourselves: skip SlopBoard's own dashboard window.
        if raw_title == OWN_WINDOW_TITLE:
            return None

        # Browsers get a stable name; other apps use the cleaned window title,
        # falling back to the process name when the window has no title at all.
        display = (KNOWN_APPS.get(process_name.lower())
                   or clean_title(raw_title) or process_name)

        # Games launched via Steam/Epic/GOG live under a recognisable folder.
        # If the exe path looks like a game, tag the name so it categorises as
        # a game even when we can't get a nice window title (e.g. fullscreen).
        try:
            exe_path = (proc.exe() or "").lower()
        except Exception:
            exe_path = ""
        game_markers = ["steamapps", "steam\\steamapps", "epic games",
                        "gog galaxy", "riot games"]
        if any(marker in exe_path for marker in game_markers):
            display = f"{display} [game]"      # the loader reads this tag

        return process_name, display
    except Exception:
        return None


def load_today(today: str) -> DayTotals:
    """Read today's existing totals from the CSV into {app: (name, seconds)}."""
    totals: DayTotals = {}
    if APP_CSV.exists():
        with APP_CSV.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row.get("date") != today:
                    continue
                app = row["app"]
                name = row.get("name") or app        # fall back for old files
                seconds = int(float(row.get("seconds") or 0))
                totals[app] = (name, seconds)
    return totals


def save_totals(today: str, totals: DayTotals) -> None:
    """Save today's totals, leaving every other day's rows untouched.

    Rewriting the whole (small) file is the simplest safe approach.
    """
    APP_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Keep the rows for all the other days.
    other_days: list[dict] = []
    if APP_CSV.exists():
        with APP_CSV.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row.get("date") != today:
                    other_days.append(row)

    # Write the other days back, then today's fresh totals.
    with APP_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["date", "app", "name", "seconds"])
        writer.writeheader()
        writer.writerows(other_days)
        for app, (name, seconds) in sorted(totals.items()):
            writer.writerow({"date": today, "app": app, "name": name,
                             "seconds": seconds})


def run_real() -> None:
    """Track the real foreground app until stopped (Ctrl+C or the stop flag)."""
    # Stop here if another tracker is already running.
    lock = acquire_single_instance()
    if lock is None:
        log("Another tracker is already running. Exiting.")
        return

    # Make sure we can actually read the active window (Windows + libraries).
    if not tracking_supported():
        log("Could not read the active window. This needs Windows with "
            "pywin32 and psutil:\n    pip install pywin32 psutil")
        return

    today = date.today().isoformat()
    totals = load_today(today)
    STOP_FLAG.unlink(missing_ok=True)   # clear any leftover flag from last time
    log(f"Tracking started. Writing to {APP_CSV}\nPress Ctrl+C to stop.")

    samples = 0
    try:
        while True:
            time.sleep(SAMPLE_SECONDS)

            # Stop if the dashboard's "Stop tracking" button asked us to.
            if STOP_FLAG.exists():
                STOP_FLAG.unlink(missing_ok=True)
                save_totals(today, totals)
                log("Stop requested. Tracker exiting.")
                break

            # At midnight, save and start a fresh day.
            now = date.today().isoformat()
            if now != today:
                save_totals(today, totals)
                today = now
                totals = load_today(today)

            # Add this interval to whichever app is in focus.
            current = active_app()
            if current:
                process_name, title = current
                _, seconds = totals.get(process_name, (title, 0))
                totals[process_name] = (title, seconds + SAMPLE_SECONDS)

            # Save to disk every so often.
            samples += 1
            if samples % FLUSH_EVERY == 0:
                save_totals(today, totals)
    except KeyboardInterrupt:
        save_totals(today, totals)
        log("Stopped. Data saved.")


def run_simulate() -> None:
    """Write one day of fake data, so the app can be tested without Windows."""
    import random

    today = date.today().isoformat()
    rng = random.Random()
    # process name -> (friendly window title, seconds)
    fake: DayTotals = {
        "chrome.exe": ("Google Chrome", rng.randint(1800, 7200)),
        "Code.exe": ("Visual Studio Code", rng.randint(1800, 6000)),
        "spotify.exe": ("Spotify", rng.randint(600, 3000)),
        "Discord.exe": ("Discord", rng.randint(300, 1500)),
        "SC2_x64.exe": ("StarCraft II", rng.randint(600, 3600)),
    }

    totals = load_today(today)
    for app, (name, seconds) in fake.items():
        _, existing = totals.get(app, (name, 0))
        totals[app] = (name, existing + seconds)
    save_totals(today, totals)

    print(f"Wrote simulated data for {today} to {APP_CSV}")
    for app, (name, seconds) in sorted(fake.items()):
        print(f"  {name} ({app}): {seconds // 60}m")


if __name__ == "__main__":
    set_process_name("SlopBoard tracker")
    if "--simulate" in sys.argv:
        run_simulate()
    else:
        run_real()
