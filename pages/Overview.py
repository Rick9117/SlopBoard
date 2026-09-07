"""
The Overview page: this week's summary.

Shows the most-watched platform and most-used app, the top categories, and a
per-day chart of time spent.
"""

import altair as alt
import pandas as pd
import streamlit as st

from core import common, categories


def category_row_html(category: str, minutes: float) -> str:
    """Return the HTML for one 'Top Categories' row: coloured name, time right."""
    colour = categories.color_for_category(category)
    return f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:10px 14px;margin-bottom:6px;background:#1A1D26;
                border-left:4px solid {colour};border-radius:8px;font-size:15px;">
      <span style="color:{colour};font-weight:700;">{category}</span>
      <span style="color:#10B981;font-weight:700;">{common.fmt_minutes(minutes)}</span>
    </div>"""


def daily_chart(daily: pd.Series) -> alt.Chart:
    """Build the 'time per day' bar chart (hours on the axis, capped at 24h)."""
    data = daily.reset_index()
    data.columns = ["Date", "Minutes"]
    data["Minutes"] = data["Minutes"].clip(upper=1440)        # cap at 24 hours
    data["Hours"] = (data["Minutes"] / 60).round(2)
    data["Time"] = data["Minutes"].apply(common.fmt_minutes)   # readable tooltip
    data["Label"] = pd.to_datetime(data["Date"]).dt.strftime("%a %d %b")

    return (
        alt.Chart(data)
        .mark_bar(color="#10B981", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Label:N", sort=list(data["Label"]),
                    axis=alt.Axis(labelAngle=0, title=None)),
            y=alt.Y("Hours:Q", axis=alt.Axis(title="Hours")),
            tooltip=[alt.Tooltip("Label:N", title="Day"),
                     alt.Tooltip("Time:N", title="Time")],
        )
        .properties(height=280)
    )


# --- Load this week's data ---
folder = st.session_state.get("slopper_folder", str(common.DEFAULT_SLOPPER_FOLDER))
data, used_sample = common.get_data(folder)

st.title("Overview")
st.caption("Your habits this week (Monday – Sunday)")

# On first run there's no data, so point the user at Slopper.
if used_sample:
    st.warning(
        f"No data found yet, so this is **sample data**. Install the "
        f"[Slopper extension]({common.SLOPPER_EXTENSION_URL}) to track your "
        f"web slop, and start the desktop tracker to track the apps you actively use."
    )

this_week = common.filter_this_week(data)
web_week = this_week[this_week["source"] == "web"]
app_week = this_week[this_week["source"] == "app"]

if this_week.empty:
    st.info("No data for this week yet.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Metrics: total slop, most-watched platform, most-used app ---
slop_total = web_week["minutes"].sum()
platforms = common.totals_by_display(web_week)
apps = common.totals_by_display(app_week)

col1, col2, col3 = st.columns(3)
col1.metric("Slop this week", common.fmt_minutes(slop_total))
if not platforms.empty:
    col2.metric("Most-watched", platforms.index[0],
                common.fmt_minutes(platforms.iloc[0]))
else:
    col2.metric("Most-watched", "—")
# Most-used app excludes slop (it only looks at desktop apps).
if not apps.empty:
    col3.metric("Most-used app", apps.index[0], common.fmt_minutes(apps.iloc[0]))
else:
    col3.metric("Most-used app", "—")

# --- Top platforms (web slop, coloured bars) ---
if not web_week.empty:
    st.subheader("Top Platforms")
    st.markdown(common.render_app_bars(common.apps_in_category(web_week, categories.SLOP)),
                unsafe_allow_html=True)

# --- Top categories (apps + web) as name | time ---
st.subheader("Top Categories")
category_totals = common.category_totals_ordered(this_week)
if not category_totals:
    st.caption("No categories yet.")
else:
    html = "".join(category_row_html(cat, mins) for cat, mins in category_totals)
    st.markdown(html, unsafe_allow_html=True)

# --- Time per day ---
st.subheader("Time per day")
st.caption("Total time per day this week.")
daily = common.daily_totals(web_week if not web_week.empty else this_week)
if daily.empty:
    st.caption("No daily data yet.")
else:
    st.altair_chart(daily_chart(daily), width="stretch")

common.sidebar_status(data, used_sample, folder)
