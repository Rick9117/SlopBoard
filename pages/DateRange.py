"""
The Date range page: how a chosen week or month looked, day by day.

A granularity toggle picks Week (Monday–Sunday) or Month; the picker then lists
the weeks or months you have data for, and the chart shows one bar per day.
"""

import altair as alt
import pandas as pd
import streamlit as st

from core import common


def daily_chart(by_day: pd.Series, days: list[pd.Timestamp],
                labels: list[str]) -> alt.Chart:
    """Build a one-bar-per-day chart for a span of days (hours on the axis, 0-24).

    `by_day` maps a date to minutes; `days` is every day in the span (so empty
    days still show a zero bar); `labels` is the matching x-axis text.
    """
    frame = pd.DataFrame({
        "Label": labels,
        "Minutes": [min(float(by_day.get(d.date(), 0)), 1440) for d in days],
    })
    frame["Hours"] = (frame["Minutes"] / 60).round(2)
    frame["Time"] = frame["Minutes"].apply(common.fmt_minutes)      # readable tooltip

    return (
        alt.Chart(frame)
        .mark_bar(color="#10B981", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Label:N", sort=labels,
                    axis=alt.Axis(labelAngle=0, title=None)),
            # Fix the axis to a full day (0-24h) so bars are comparable.
            y=alt.Y("Hours:Q", scale=alt.Scale(domain=[0, 24]),
                    axis=alt.Axis(title="Hours", values=list(range(0, 25, 4)))),
            tooltip=[alt.Tooltip("Label:N", title="Day"),
                     alt.Tooltip("Time:N", title="Time")],
        )
        .properties(height=300)
    )


# --- Load data ---
folder = st.session_state.get("slopper_folder", str(common.DEFAULT_SLOPPER_FOLDER))
data, used_sample = common.get_data(folder)

st.title("Date range")
st.caption("Your activity across a chosen week or month")

if data.empty:
    st.info("No data yet.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Granularity toggle: a week (Mon-Sun) or a whole month ---
granularity = st.radio("View by", ["Week", "Month"], horizontal=True)

if granularity == "Week":
    # One entry per week we have data for, newest first; ISO-week labels.
    starts = sorted({common.week_start(d) for d in data["date"]}, reverse=True)
    labels = [common.week_label(s, index=common.iso_week_number(s)) for s in starts]
    choice = st.selectbox("Pick a week", labels, index=0)
    start = starts[labels.index(choice)]
    end = start + pd.Timedelta(days=7)
    days = list(pd.date_range(start, periods=7))
    x_labels = [d.strftime("%A") for d in days]            # Monday, Tuesday, ...
    total_label = "Total this week"
else:
    # One entry per month we have data for, newest first.
    starts = sorted({common.month_start(d) for d in data["date"]}, reverse=True)
    labels = [common.month_label(s) for s in starts]
    choice = st.selectbox("Pick a month", labels, index=0)
    start = starts[labels.index(choice)]
    end = start + pd.offsets.MonthBegin(1)                 # first day of next month
    days = list(pd.date_range(start, end - pd.Timedelta(days=1)))
    x_labels = [d.strftime("%d").lstrip("0") for d in days]   # day numbers 1..31
    total_label = "Total this month"

# --- Filter to the chosen period ---
period = data[(data["date"] >= start) & (data["date"] < end)]

if period.empty:
    st.info("Nothing recorded in that period.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Metrics (all scoped to the chosen period) ---
total = period["minutes"].sum()
days_active = period["date"].dt.date.nunique()
platforms = common.totals_by_display(period[period["source"] == "web"])
apps = common.totals_by_display(period[period["source"] == "app"])

col1, col2, col3, col4 = st.columns(4)
col1.metric(total_label, common.fmt_minutes(total))
col2.metric("Daily average", common.fmt_minutes(total / max(days_active, 1)))
if not platforms.empty:
    col3.metric("Most-watched", platforms.index[0],
                common.fmt_minutes(platforms.iloc[0]))
else:
    col3.metric("Most-watched", "—")
# Most-used app excludes slop (it only looks at desktop apps).
if not apps.empty:
    col4.metric("Most-used app", apps.index[0], common.fmt_minutes(apps.iloc[0]))
else:
    col4.metric("Most-used app", "—")

# --- Daily chart ---
st.subheader("Activity per day")
by_day = period.groupby(period["date"].dt.date)["minutes"].sum()
st.altair_chart(daily_chart(by_day, days, x_labels), width="stretch")

# --- Where the time went: apps grouped by category (Slop first), max 10 each ---
st.subheader("Where the time went")
common.render_apps_by_category(period, max_rows=10)

common.sidebar_status(data, used_sample, folder)
