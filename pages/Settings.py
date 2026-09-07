"""
The Settings page.

Choose where to read Slopper's files, start or stop the desktop tracker, turn
auto-start on or off, and switch between dark and light themes.
"""

import socket
import tomllib
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from core import common, startup

# Must match LOCK_PORT in tracker/app_tracker.py.
TRACKER_LOCK_PORT: int = 50505

# Where Streamlit reads the theme from.
CONFIG_PATH: Path = common.ROOT / ".streamlit" / "config.toml"


def tracker_running() -> bool:
    """Return True if the tracker holds its single-instance lock (i.e. is alive).

    We try to bind the same port the tracker locks. If the bind fails, the port
    is taken, which means the tracker is running.
    """
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", TRACKER_LOCK_PORT))
        probe.close()
        return False
    except OSError:
        return True


def current_theme() -> str:
    """Return the theme base ("dark" or "light") from the config file."""
    try:
        with CONFIG_PATH.open("rb") as handle:
            return tomllib.load(handle).get("theme", {}).get("base", "dark")
    except Exception:
        return "dark"


def set_theme(base: str) -> None:
    """Write the chosen theme base into .streamlit/config.toml.

    Streamlit reads the theme at startup, so the change fully applies after a
    restart. We rewrite the whole file from known settings to keep it simple.
    """
    dark = base == "dark"
    background = "#0E1117" if dark else "#FFFFFF"
    secondary = "#1A1D26" if dark else "#F0F2F6"
    text = "#EAF5F0" if dark else "#1A1A1A"

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        "# SlopBoard theme. Changed from the Settings page.\n\n"
        "[theme]\n"
        f'base = "{base}"\n'
        'primaryColor = "#10B981"\n'
        f'backgroundColor = "{background}"\n'
        f'secondaryBackgroundColor = "{secondary}"\n'
        f'textColor = "{text}"\n\n'
        "[browser]\n"
        "gatherUsageStats = false\n",
        encoding="utf-8",
    )


st.title("Settings")

# --- Slopper data folder ---
st.subheader("Slopper data folder")
st.caption("Where SlopBoard looks for Slopper's exported files.")
current_folder = st.session_state.get("slopper_folder", str(common.DEFAULT_SLOPPER_FOLDER))
new_folder = st.text_input("Folder path", value=current_folder)
if new_folder != current_folder:
    st.session_state.slopper_folder = new_folder
    common.get_data.clear()          # the data source changed, so drop the cache
    st.success("Folder updated. Data will reload.")

# Point the user to the extension if this folder has no Slopper data.
if not common.has_slopper_data(new_folder):
    st.markdown(common.slopper_missing_note(), unsafe_allow_html=True)

# --- Tracker status and Stop button ---
st.subheader("Desktop tracker")
st.caption("Records the app in your active (focused) window every few seconds. "
           "Apps running in the background aren't counted.")
if tracker_running():
    st.success("Tracker is running in the background.")
    if st.button("Stop tracking", type="primary"):
        (common.DATA_DIR / "stop.flag").touch()
        st.toast("App tracking has stopped.")
        st.info("App tracking has stopped. It will save and exit within a few "
                "seconds. Restart it by double-clicking **run_slopboard.bat**.")
else:
    st.warning("Tracker is not running.")
    st.caption("Start everything by double-clicking **run_slopboard.bat**, or run "
               "just the tracker with `py tracker/app_tracker.py` "
               "(add `--simulate` to test without Windows).")

# Show how much the tracker has recorded today, if anything.
if common.APP_CSV.exists():
    try:
        app_data = pd.read_csv(common.APP_CSV)
        today_rows = app_data[app_data["date"] == date.today().isoformat()]
        if not today_rows.empty:
            minutes = int(today_rows["seconds"].sum() // 60)
            st.caption(f"Recorded today: {minutes} minutes across "
                       f"{today_rows['app'].nunique()} apps.")
    except Exception:
        pass

# --- Auto-start on boot ---
st.subheader("Start tracking automatically")
is_on = startup.is_enabled()
want_on = st.toggle("Start the tracker when Windows starts", value=is_on)
if want_on != is_on:
    changed = startup.enable() if want_on else startup.disable()
    if changed and want_on:
        st.success("The tracker will now start automatically when you turn on your PC.")
    elif changed and not want_on:
        st.info("Auto-start turned off. The tracker will only run when you launch "
                "SlopBoard.")
    else:
        st.warning("Could not change the auto-start setting. This feature is "
                   "Windows-only.")

# --- Appearance (dark / light theme) ---
st.subheader("Appearance")
dark_now = current_theme() == "dark"
want_dark = st.toggle("Dark mode", value=dark_now)
if want_dark != dark_now:
    set_theme("dark" if want_dark else "light")
    st.info("Theme changed. Refresh the page (or reopen SlopBoard) to see it.")
