"""
The data loader: reads the two local sources and combines them.

  1. Slopper's JSON files in the Downloads/slopper folder (web slop).
  2. The desktop tracker's CSV, data/app_activity.csv (desktop apps).

Both are flattened into one table and saved to data/slopboard.csv. Everything is
plain local files - no SQL. Columns in the combined table:
  date, source, key, display, category, seconds, minutes
where `key` is the stable identifier (process name or platform) and `display` is
the friendly name shown in the UI (window title or platform label).
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from core import categories

# One activity row: (iso_date, key, display_name, seconds).
Row = tuple[str, str, str, int]

# Slopper's five platforms and how to display them.
WEB_PLATFORMS: list[str] = ["youtube", "instagram", "tiktok", "facebook", "twitter"]
WEB_LABELS: dict[str, str] = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "facebook": "Facebook",
    "twitter": "X (Twitter)",
}


def _read_slopper_json(file: Path) -> dict:
    """Read one Slopper JSON file and return its {date: {platform: seconds}}."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if data.get("source") != "slopper":
        return {}
    return data.get("days", {})


def _read_slopper_csv(file: Path) -> dict:
    """Read one Slopper CSV file and return its {date: {platform: seconds}}.

    (Slopper writes JSON today; this supports a possible future CSV export.)
    """
    days: dict[str, dict] = {}
    try:
        with file.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                day = row.get("date")
                if not day:
                    continue
                days[day] = {p: int(float(row[p])) for p in WEB_PLATFORMS if row.get(p)}
    except OSError:
        pass
    return days


def load_slopper_folder(folder: str | Path) -> list[Row]:
    """Read all Slopper files in a folder and return web activity rows.

    For web platforms the key and display name are the same (the platform label).
    Later files win when the same date appears twice.
    """
    folder = Path(folder)
    if not folder.exists():
        return []

    days: dict[str, dict] = {}
    for file in sorted(folder.glob("slopper-*.json")):
        days.update(_read_slopper_json(file))
    for file in sorted(folder.glob("slopper-*.csv")):
        days.update(_read_slopper_csv(file))

    rows: list[Row] = []
    for day, totals in days.items():
        for platform in WEB_PLATFORMS:
            seconds = int(totals.get(platform, 0) or 0)
            if seconds > 0:
                label = WEB_LABELS[platform]
                rows.append((day, label, label, seconds))
    return rows


def clean_display(name: str) -> str:
    """Reduce a messy stored display name to just the app name.

    Old data (and some window titles) look like "Friends - Discord" or
    "SlopBoard - Google Chrome - (chrome.exe)". The real app name is the last
    " - " segment, ignoring any trailing "(process.exe)" the old tracker added.
    """
    text = name.strip()

    # Drop a trailing "(something.exe)" the old tracker used to append.
    if text.endswith(")") and "(" in text:
        text = text[:text.rfind("(")].strip().rstrip("-").strip()

    # Take the last " - " segment, which is where the app name lives.
    if " - " in text:
        text = text.rsplit(" - ", 1)[-1].strip()
    return text


def load_app_csv(path: str | Path) -> list[Row]:
    """Read the tracker's CSV and return (date, process, display, seconds) rows."""
    path = Path(path)
    if not path.exists():
        return []

    rows: list[Row] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            day = (row.get("date") or "").strip()
            key = (row.get("app") or "").strip()
            raw = (row.get("name") or key).strip()      # fall back for old files
            # Clean here too, so old messy rows are fixed on read.
            display = clean_display(raw) or key
            seconds = int(float(row.get("seconds") or 0))
            if day and key and seconds > 0:
                rows.append((day, key, display, seconds))
    return rows


def make_sample(weeks: int = 4) -> tuple[list[Row], list[Row]]:
    """Return believable fake (web_rows, app_rows) so the dashboard is never empty."""
    rng = random.Random(42)          # fixed seed = same demo every run
    today = date.today()

    web_base = {"youtube": 900, "instagram": 400, "tiktok": 600,
                "facebook": 120, "twitter": 200}
    # process name -> friendly display name
    app_base = {
        "chrome.exe": "Google Chrome",
        "Code.exe": "Visual Studio Code",
        "spotify.exe": "Spotify",
        "SC2_x64.exe": "StarCraft II",
        "Discord.exe": "Discord",
        "Teams.exe": "Microsoft Teams",
    }
    app_seconds = {"chrome.exe": 4000, "Code.exe": 3000, "spotify.exe": 1500,
                   "SC2_x64.exe": 1200, "Discord.exe": 700, "Teams.exe": 600}

    web_rows: list[Row] = []
    app_rows: list[Row] = []
    for days_ago in range(weeks * 7):
        day_date = today - timedelta(days=days_ago)
        day = day_date.isoformat()
        weekend = day_date.weekday() >= 5

        for platform, base in web_base.items():
            ceiling = int(base * (1.6 if weekend else 1.0))
            seconds = 0 if rng.random() < 0.3 else rng.randint(0, ceiling)
            if seconds:
                label = WEB_LABELS[platform]
                web_rows.append((day, label, label, seconds))

        for process, base in app_seconds.items():
            ceiling = int(base * (0.5 if weekend and "Code" in process else 1.0))
            seconds = 0 if rng.random() < 0.25 else rng.randint(0, ceiling)
            if seconds:
                app_rows.append((day, process, app_base[process], seconds))

    return web_rows, app_rows


def _categorise_app(key: str, display: str, learned: dict[str, str],
                    learned_path: Path) -> str:
    """Return an app's category, learning (and saving) it the first time we see it.

    `display` may carry a "[game]" tag from the tracker. New apps are remembered
    so their category persists. If an app was previously saved as "Other" but now
    matches a real rule (e.g. we added it to the built-ins), we upgrade it.
    """
    category = categories.category_for(key, learned, is_web=False, display=display)
    clean_key = categories._clean(key)      # same cleaning used everywhere

    previous = learned.get(clean_key)
    # Save the first time, or upgrade a stale "Other" to a real category.
    if previous is None or (previous == categories.OTHER and category != categories.OTHER):
        categories.remember(key, category, learned_path)
        learned[clean_key] = category
    return category


def to_frame(web_rows: list[Row], app_rows: list[Row],
             learned: dict[str, str], learned_path: Path) -> pd.DataFrame:
    """Combine web and app rows into one categorised DataFrame.

    New desktop apps are learned as a side effect (see _categorise_app).
    Columns: date, source, key, display, category, seconds, minutes.
    """
    columns = ["date", "source", "key", "display", "category", "seconds", "minutes"]
    records: list[dict] = []

    for day, key, display, seconds in web_rows:
        records.append({"date": day, "source": "web", "key": key, "display": display,
                        "category": categories.SLOP, "seconds": seconds})

    for day, key, display, seconds in app_rows:
        category = _categorise_app(key, display, learned, learned_path)
        # Strip the "[game]" tag so it isn't shown in the UI.
        clean_display = display.replace("[game]", "").strip()
        records.append({"date": day, "source": "app", "key": key,
                        "display": clean_display, "category": category,
                        "seconds": seconds})

    if not records:
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    # Keep full precision (don't round to 0.1 min); fmt_minutes rounds only for
    # display, so 10s stays 10s instead of snapping to 0.2 min (shown as "12s").
    frame["minutes"] = frame["seconds"] / 60
    return frame.sort_values("date")


def save_combined(frame: pd.DataFrame, path: str | Path) -> None:
    """Save the combined table to CSV, writing dates as plain YYYY-MM-DD."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    out = frame.copy()
    if not out.empty:
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
