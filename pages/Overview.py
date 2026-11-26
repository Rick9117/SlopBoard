"""
The Overview page: today at a glance.

Shows today's slop time, the most-watched platform and most-used app, the top
categories, and a breakdown of today's apps grouped by category.
"""

import streamlit as st

from core import common, categories


def category_row_html(category: str, minutes: float) -> str:
    """Return the HTML for one 'Top categories' row: coloured name, time right."""
    colour = categories.color_for_category(category)
    return f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:10px 14px;margin-bottom:6px;background:#1A1D26;
                border-left:4px solid {colour};border-radius:8px;font-size:15px;">
      <span style="color:{colour};font-weight:700;">{category}</span>
      <span style="color:#10B981;font-weight:700;">{common.fmt_minutes(minutes)}</span>
    </div>"""


# --- Load today's data ---
folder = st.session_state.get("slopper_folder", str(common.DEFAULT_SLOPPER_FOLDER))
data, used_sample = common.get_data(folder)

st.title("Overview")
st.caption("Your habits today")

# On first run there's no data, so point the user at Slopper.
if used_sample:
    st.warning(
        f"No data found yet, so this is **sample data**. Install the "
        f"[Slopper extension]({common.SLOPPER_EXTENSION_URL}) to track your "
        f"web slop, and start the desktop tracker to track the apps you actively use."
    )

today = common.filter_today(data)
web_today = today[today["source"] == "web"]
app_today = today[today["source"] == "app"]

if today.empty:
    st.info("No activity recorded today yet.")
    common.sidebar_status(data, used_sample, folder)
    st.stop()

# --- Metrics: slop today, most-watched platform, most-used app ---
slop_total = web_today["minutes"].sum()
platforms = common.totals_by_display(web_today)
apps = common.totals_by_display(app_today)

col1, col2, col3 = st.columns(3)
col1.metric("Slop today", common.fmt_minutes(slop_total))
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

# --- Top platforms (today's web slop, coloured bars) ---
if not web_today.empty:
    st.subheader("Top platforms")
    st.markdown(common.render_app_bars(common.apps_in_category(web_today, categories.SLOP)),
                unsafe_allow_html=True)

# --- Top categories (apps + web) as name | time ---
st.subheader("Top categories")
category_totals = common.category_totals_ordered(today)
if not category_totals:
    st.caption("No categories yet.")
else:
    html = "".join(category_row_html(cat, mins) for cat, mins in category_totals)
    st.markdown(html, unsafe_allow_html=True)

# --- Where the time went: apps grouped by category, Slop first ---
st.subheader("Where the time went")
common.render_apps_by_category(today, max_rows=10)

common.sidebar_status(data, used_sample, folder)
