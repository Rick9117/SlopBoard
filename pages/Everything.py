"""
The Everything page: desktop apps and web slop together - the whole day at once.

Its trick is showing how much of the browser's time was slop, which needs both
data sources (the tracker and Slopper) at the same time.
"""

import streamlit as st

from core import common, categories


# --- Load data ---
folder = st.session_state.get("slopper_folder", str(common.DEFAULT_SLOPPER_FOLDER))
data, used_sample = common.get_data(folder)

st.title("Everything")
st.caption("All activity today — desktop apps and web slop together")

# Tell the user if a data source is missing (the app still works either way).
has_app_data = (not data.empty) and (data["source"] == "app").any()
if used_sample:
    st.warning(f"Showing **sample data**. Start the desktop tracker and install "
               f"[Slopper]({common.SLOPPER_EXTENSION_URL}) to see your real activity.")
elif not has_app_data:
    st.info("No desktop-tracker data yet — showing web slop only. Run "
            "`py tracker/app_tracker.py` to track the app in your active window.")

# Keep only today's rows.
today = data[data["date"].dt.date == data["date"].dt.date.max()] if not data.empty else data

if today.empty:
    st.info("No activity recorded yet.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Metrics ---
total_minutes = today["minutes"].sum()
slop_minutes = today[today["source"] == "web"]["minutes"].sum()
apps = common.totals_by_display(today)

col1, col2, col3 = st.columns(3)
col1.metric("Active today", common.fmt_minutes(total_minutes))
col2.metric("Of which slop", common.fmt_minutes(slop_minutes))
col3.metric("Top item", apps.index[0] if not apps.empty else "—")

# --- Top applications, grouped by category, max 10 each (expandable) ---
st.subheader("Top Applications")
common.render_apps_by_category(today, max_rows=10)

# --- Browser slop breakdown ---
st.subheader("Browser breakdown")
web_today = today[today["source"] == "web"]
if web_today.empty:
    st.caption("No web slop tracked today.")
else:
    web_total = web_today["minutes"].sum()
    st.markdown(f"Of today's browsing, **{common.fmt_minutes(web_total)}** was slop:")
    st.markdown(common.render_app_bars(common.apps_in_category(web_today, categories.SLOP),
                                       max_rows=5),
                unsafe_allow_html=True)

common.sidebar_status(data, used_sample, folder)
