"""
The Weekly page: how a chosen week looked, day by day (Monday to Sunday).
"""

import altair as alt
import pandas as pd
import streamlit as st

from core import common

# Full day names, in the correct Monday..Sunday order (used to sort the chart).
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def weekly_chart(week: pd.DataFrame, start: pd.Timestamp) -> alt.Chart:
    """Build the Mon-Sun bar chart for one week (hours on the axis, 0-24)."""
    by_day = week.groupby(week["date"].dt.date)["minutes"].sum()
    days = pd.date_range(start, periods=7)

    data = pd.DataFrame({
        "Day": [d.strftime("%A") for d in days],                       # Monday...
        "Minutes": [min(float(by_day.get(d.date(), 0)), 1440) for d in days],
    })
    data["Hours"] = (data["Minutes"] / 60).round(2)
    data["Time"] = data["Minutes"].apply(common.fmt_minutes)           # tooltip

    return (
        alt.Chart(data)
        .mark_bar(color="#10B981", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Day:N", sort=DAY_ORDER,
                    axis=alt.Axis(labelAngle=0, title=None)),          # upright
            # Fix the axis to a full day (0-24h) so bars are comparable.
            y=alt.Y("Hours:Q", scale=alt.Scale(domain=[0, 24]),
                    axis=alt.Axis(title="Hours", values=list(range(0, 25, 4)))),
            tooltip=[alt.Tooltip("Day:N"), alt.Tooltip("Time:N", title="Time")],
        )
        .properties(height=300)
    )


# --- Load data ---
folder = st.session_state.get("slopper_folder", str(common.DEFAULT_SLOPPER_FOLDER))
data, used_sample = common.get_data(folder)

st.title("Weekly")
st.caption("Your activity across a chosen week")

if data.empty:
    st.info("No data yet.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Week picker: one entry per week we have data for, newest first ---
# Labels use the real calendar week number (ISO), e.g. "(Week 36) Monday...".
mondays = sorted({common.week_start(d) for d in data["date"]}, reverse=True)
labels = [common.week_label(monday, index=common.iso_week_number(monday))
          for monday in mondays]
choice = st.selectbox("Pick a week", labels, index=0)
chosen_monday = mondays[labels.index(choice)]

# --- Filter to the chosen week ---
start = chosen_monday
end = start + pd.Timedelta(days=7)
week = data[(data["date"] >= start) & (data["date"] < end)]

if week.empty:
    st.info("Nothing recorded that week.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Metrics ---
total = week["minutes"].sum()
days_active = week["date"].dt.date.nunique()
col1, col2 = st.columns(2)
col1.metric("Total this week", common.fmt_minutes(total))
col2.metric("Daily average", common.fmt_minutes(total / max(days_active, 1)))

# --- Daily chart ---
st.subheader("Weekly activity")
st.caption("Total time per day for the chosen week.")
st.altair_chart(weekly_chart(week, start), width="stretch")

# --- Where the time went: apps grouped by category (Slop first), max 10 each ---
st.subheader("Where the time went")
common.render_apps_by_category(week, max_rows=10)

common.sidebar_status(data, used_sample, folder)
