"""
Shared helpers used by every page: file paths, the colour map, the cached
data-loading function, and small formatting/aggregation/rendering utilities.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from core import data_loader, categories

# ---------------------------------------------------------------- file paths
ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = ROOT / "data"
APP_CSV: Path = DATA_DIR / "app_activity.csv"           # the tracker writes this
COMBINED_CSV: Path = DATA_DIR / "slopboard.csv"         # the combined "database"
LEARNED_CSV: Path = DATA_DIR / "learned_categories.csv"  # remembered app categories

# Default place Slopper writes its files.
DEFAULT_SLOPPER_FOLDER: Path = Path.home() / "Downloads" / "slopper"

# Where to get Slopper - shown when no Slopper data is found.
SLOPPER_EXTENSION_URL: str = ("https://chromewebstore.google.com/detail/"
                              "slopper-brainrotslop-stop/"
                              "agdjpbclibfpgkmhjmhjmopogmmnmmac")


def has_slopper_data(folder: str) -> bool:
    """Return True if the Slopper folder holds any real exported activity."""
    return bool(data_loader.load_slopper_folder(folder))


def slopper_missing_note() -> str:
    """HTML for a red note prompting the user to install the Slopper extension."""
    return (f"<div style='color:#F87171;font-size:0.9rem;line-height:1.4;'>"
            f"No Slopper data found — "
            f"<a href='{SLOPPER_EXTENSION_URL}' target='_blank' "
            f"style='color:#F87171;text-decoration:underline;'>"
            f"get the Slopper extension here</a>.</div>")

# Hide apps you barely touched. The tracker samples every few seconds, so brief
# system windows (Search, Task Manager, an Explorer click) would otherwise clutter
# the lists. Lower this to show shorter sessions; set it to 0 to show everything.
MIN_DISPLAY_SECONDS: int = 60

# ---------------------------------------------------------------- colours
# Bars grow and change colour with how much time was spent, like the Slopper
# extension: a little time is a short green bar, and as it fills it shifts green
# -> yellow -> orange, turning red once the bar is completely full at 2 hours.
# So "good" (low) reads green and small, "bad" (high) reads red and full.
FULL_BAR_MINUTES: int = 120        # 2 hours = a completely full (red) bar


def _bar_style(minutes: float) -> tuple[float, str]:
    """Return (width_percent, colour) for a bar from the time spent.

    Width is proportional to the time, filling up at FULL_BAR_MINUTES (2h). The
    colour is keyed to how full the bar is: green up to a third, yellow to two
    thirds, orange up to full, and red once it's full (2h or more).
    """
    fill = minutes / FULL_BAR_MINUTES * 100      # % of the way to full (can exceed 100)
    width = max(min(fill, 100.0), 2.0)           # clamp to the bar; keep a visible sliver
    if fill >= 100:
        colour = "#EF4444"            # red - full (2h+)
    elif fill >= 67:
        colour = "#F97316"            # orange
    elif fill >= 33:
        colour = "#EAB308"            # yellow
    else:
        colour = "#22C55E"            # green - just a little
    return width, colour


# ---------------------------------------------------------------- data loading
@st.cache_data
def get_data(slopper_folder: str) -> tuple[pd.DataFrame, bool]:
    """Load both sources, combine them, save the combined CSV, and return it.

    Returns (dataframe, used_sample). Cached, so it only re-runs when the folder
    changes or the cache is cleared (the Refresh button clears it). Falls back to
    sample data if nothing real is found, so the dashboard is never empty.
    """
    learned = categories.load_learned(LEARNED_CSV)
    web_rows = data_loader.load_slopper_folder(slopper_folder)
    app_rows = data_loader.load_app_csv(APP_CSV)

    # Heal any old, bloated learned file: load_learned normalises the keys, so
    # writing it straight back collapses duplicate/".exe" rows to one per app.
    if learned:
        categories.save_learned(learned, LEARNED_CSV)

    used_sample = False
    if not web_rows and not app_rows:
        web_rows, app_rows = data_loader.make_sample()
        used_sample = True

    frame = data_loader.to_frame(web_rows, app_rows, learned, LEARNED_CSV)
    data_loader.save_combined(frame, COMBINED_CSV)
    return frame, used_sample


# ---------------------------------------------------------------- formatting
def fmt_minutes(total_minutes: float) -> str:
    """Format a duration for display: 0.4 -> '24s', 36 -> '36m', 95 -> '1h 35m'.

    Sub-minute durations are shown in seconds so short sessions (e.g. a game you
    only just opened) read honestly instead of rounding down to a bare '0m'.
    """
    total_seconds = int(round(total_minutes * 60))
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def week_start(day: pd.Timestamp | str) -> pd.Timestamp:
    """Return the Monday of the week the given date falls in."""
    day = pd.Timestamp(day).normalize()
    return day - pd.Timedelta(days=day.weekday())


def iso_week_number(day: pd.Timestamp | str) -> int:
    """Return the ISO calendar week number (1-53) for a date."""
    return int(pd.Timestamp(day).isocalendar().week)


def filter_this_week(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows whose date is in the current week (Mon-Sun)."""
    if frame.empty:
        return frame
    start = week_start(pd.Timestamp.today())
    end = start + pd.Timedelta(days=7)
    return frame[(frame["date"] >= start) & (frame["date"] < end)]


# ---------------------------------------------------------------- aggregation
def _best_display(names: pd.Series) -> str:
    """Pick the friendliest display name for an app.

    Prefer a real window title over a bare process name (old data, before title
    capture, stored the process name as the display). The longest non-".exe"
    name is a good heuristic for the friendly one.
    """
    real = [n for n in names.unique() if not str(n).lower().endswith(".exe")]
    if real:
        return max(real, key=len)
    return names.iloc[0]


def totals_by_display(frame: pd.DataFrame) -> pd.Series:
    """Return total minutes per app/platform, biggest first.

    Apps are grouped by their stable key (process name) so old rows (which had
    no window title) merge with new ones, and labelled with the best display name.
    """
    if frame.empty:
        return pd.Series(dtype=float)
    grouped = frame.groupby("key").agg(
        minutes=("minutes", "sum"),
        display=("display", _best_display),
    )
    grouped = grouped.set_index("display")["minutes"]
    return grouped.sort_values(ascending=False)


def totals_by_category(frame: pd.DataFrame) -> pd.Series:
    """Return total minutes per category, biggest first."""
    if frame.empty:
        return pd.Series(dtype=float)
    return frame.groupby("category")["minutes"].sum().sort_values(ascending=False)


def daily_totals(frame: pd.DataFrame) -> pd.Series:
    """Return total minutes per day, indexed by date."""
    if frame.empty:
        return pd.Series(dtype=float)
    return frame.groupby(frame["date"].dt.date)["minutes"].sum()


def category_totals_ordered(frame: pd.DataFrame) -> list[tuple[str, float]]:
    """Return (category, minutes) pairs, Slop first then most-used to least."""
    if frame.empty:
        return []
    totals = frame.groupby("category")["minutes"].sum()

    def sort_key(category: str) -> tuple[int, float]:
        # Slop always first (rank 0); then sort by most minutes.
        is_slop = 0 if category == categories.SLOP else 1
        return (is_slop, -totals[category])

    return [(cat, totals[cat]) for cat in sorted(totals.index, key=sort_key)]


def apps_in_category(frame: pd.DataFrame, category: str) -> pd.DataFrame:
    """Return one row per app in a category: display, key, minutes, source.

    Apps are grouped by their stable key so old rows (no window title) merge
    with new ones. Sorted by minutes, biggest first.
    """
    subset = frame[frame["category"] == category]
    if subset.empty:
        return pd.DataFrame(columns=["display", "key", "minutes", "source"])

    grouped = subset.groupby("key").agg(
        display=("display", _best_display),
        minutes=("minutes", "sum"),
        source=("source", "first"),
    ).reset_index()

    # Hide apps below the minimum (see MIN_DISPLAY_SECONDS) so brief blips
    # don't clutter the lists; genuine sessions stay.
    grouped = grouped[grouped["minutes"] >= MIN_DISPLAY_SECONDS / 60]
    return grouped.sort_values("minutes", ascending=False)


def week_label(monday: pd.Timestamp | str, index: int | None = None) -> str:
    """Return a readable label for a week, e.g.
    "Monday, 29 December 2025 – Sunday, 4 January 2026", with an optional
    "(Week 36)" prefix when index is given.
    """
    monday = pd.Timestamp(monday)
    sunday = monday + pd.Timedelta(days=6)

    def long_date(timestamp: pd.Timestamp) -> str:
        # %d gives "05"; lstrip("0") makes it "5". Avoids %-d (not on Windows).
        day_number = timestamp.strftime("%d").lstrip("0")
        return timestamp.strftime("%A, ") + day_number + timestamp.strftime(" %B %Y")

    span = f"{long_date(monday)} – {long_date(sunday)}"
    return f"(Week {index}) {span}" if index is not None else span


# ---------------------------------------------------------------- rendering
def _bar_html(label: str, minutes: float, width_pct: float, colour: str) -> str:
    """Return the HTML for a single bar row: label, coloured bar, then the time.

    The time sits to the right of the bar (not inside it) so it stays readable
    even when the bar is only a short green sliver.
    """
    return f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:9px;">
      <div style="width:190px;font-size:14px;font-weight:600;">{label}</div>
      <div style="flex:1;height:30px;background:#262A36;border-radius:7px;overflow:hidden;">
        <div style="width:{width_pct}%;height:100%;background:{colour};border-radius:7px;"></div>
      </div>
      <div style="width:64px;text-align:right;font-size:13px;font-weight:700;">
        {fmt_minutes(minutes)}
      </div>
    </div>"""


def render_app_bars(apps: pd.DataFrame, max_rows: int = 10) -> str:
    """Build coloured bars for a set of apps.

    `apps` has columns display, key, minutes, source (see apps_in_category).
    Desktop apps are labelled "Display - (process.exe)"; web platforms just show
    their name. Each bar's width and colour come from its time (see _bar_style).
    """
    if apps.empty:
        return "<p style='color:#8FB3A6;'>No data yet.</p>"

    bars: list[str] = []
    for _, row in apps.head(max_rows).iterrows():
        # Show the process name in brackets for desktop apps only.
        if row["source"] == "app" and row["key"] != row["display"]:
            label = f"{row['display']} - ({row['key']})"
        else:
            label = row["display"]
        width, colour = _bar_style(row["minutes"])
        bars.append(_bar_html(label, row["minutes"], width, colour))
    return "".join(bars)


def sidebar_status(frame: pd.DataFrame, used_sample: bool, folder: str) -> None:
    """Show the data-source note and a Refresh button in the sidebar."""
    st.sidebar.markdown("---")
    if used_sample:
        st.sidebar.info("Showing **sample data** - no Slopper files or tracker "
                        "data found yet.")
    else:
        days = 0 if frame.empty else frame["date"].dt.date.nunique()
        st.sidebar.caption(f"Reading local data · {days} days on record")
    st.sidebar.caption(f"Slopper folder:\n`{folder}`")

    # Nudge the user to install Slopper if we have no real web-slop data.
    has_web = (not used_sample) and (not frame.empty) and (frame["source"] == "web").any()
    if not has_web:
        st.sidebar.markdown(slopper_missing_note(), unsafe_allow_html=True)

    if st.sidebar.button("🔄 Refresh data"):
        get_data.clear()
        st.rerun()


def render_apps_by_category(frame: pd.DataFrame, max_rows: int = 10) -> None:
    """Render apps grouped by category, Slop first, each capped at max_rows.

    Each category gets a coloured, underlined header. Categories with more than
    max_rows apps get an expander ("Show all ...") for the rest.
    """
    for category, _ in category_totals_ordered(frame):
        apps = apps_in_category(frame, category)
        if apps.empty:
            continue                       # skip categories with no real activity

        colour = categories.color_for_category(category)
        st.markdown(
            f"<div style='font-size:1.15rem;font-weight:700;color:{colour};"
            f"border-bottom:2px solid {colour};padding-bottom:3px;"
            f"margin:14px 0 10px;'>{category}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(render_app_bars(apps, max_rows=max_rows), unsafe_allow_html=True)

        # If there are more apps than we showed, offer the rest in an expander.
        if len(apps) > max_rows:
            hidden = apps.iloc[max_rows:]
            with st.expander(f"Show {len(hidden)} more in {category}"):
                st.markdown(render_app_bars(hidden, max_rows=len(hidden)),
                            unsafe_allow_html=True)
