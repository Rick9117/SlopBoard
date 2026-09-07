"""
SlopBoard - a local dashboard for your screen-time habits.

Run it with:
    py -m streamlit run slopboard.py

This file is the router: it sets up shared state, injects a little styling, and
defines the sidebar menu. Each page lives in the pages/ folder.
"""

import streamlit as st

from core import common

# Give this process a friendly name in Task Manager, if setproctitle is present.
try:
    import setproctitle
    setproctitle.setproctitle("SlopBoard")
except Exception:
    pass

st.set_page_config(page_title="SlopBoard", page_icon="📊", layout="wide")

# --- Styling: bigger sidebar menu text, and a "SlopBoard" title above it ---
# The title is drawn with a ::before on the nav container, so it always sits
# above the auto-generated page menu regardless of DOM order.
st.markdown(
    """
    <style>
      /* Bigger sidebar navigation links and icons. */
      [data-testid="stSidebarNav"] a p { font-size: 1.05rem; }
      [data-testid="stSidebarNav"] a span { font-size: 1.2rem; }

      /* Lay the sidebar header as a row: title on the left, collapse arrow right. */
      [data-testid="stSidebarHeader"] {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      /* "SlopBoard" title in the top-left of the sidebar header. */
      [data-testid="stSidebarHeader"]::before {
        content: "SlopBoard";
        font-size: 1.5rem;
        font-weight: 800;
        order: -1;              /* keep it before the collapse button */
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Shared across pages: which folder to read Slopper's files from.
if "slopper_folder" not in st.session_state:
    st.session_state.slopper_folder = str(common.DEFAULT_SLOPPER_FOLDER)

# The sidebar menu, in this exact order, with clean labels.
pages = [
    st.Page("pages/Overview.py", title="Overview", icon="🏠", default=True),
    st.Page("pages/Everything.py", title="Everything", icon="📊"),
    st.Page("pages/Weekly.py", title="Weekly", icon="🗓"),
    st.Page("pages/Settings.py", title="Settings", icon="⚙"),
]

st.navigation(pages).run()
