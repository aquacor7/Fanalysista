"""Fantacalcio Analytics — multipage entry point / router.

Run from the project root:
    streamlit run src/dashboard/app.py

Uses st.navigation so the sidebar page labels can be localised — filename-based
multipage nav would otherwise hard-code them to the file names. The pages
themselves live in views/. Shared sidebar chrome (the language toggle) is
rendered *after* the active page runs, so it naturally sits at the bottom of
the sidebar without any fragile positioning CSS.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from i18n import render_language_toggle, t

st.set_page_config(page_title="Fantacalcio Analytics", layout="wide")

# Page titles are localised via t(); the active language is read from
# st.session_state["_lang"] (set by the toggle below). On a language switch
# the whole entry script re-runs, so these titles re-render translated.
pages = [
    st.Page("views/home.py", title=t("nav.home"), default=True),
    st.Page("views/league_table.py", title=t("nav.league_table")),
    st.Page("views/team_detail.py", title=t("nav.team_detail")),
    st.Page("views/player_detail.py", title=t("nav.player_detail")),
    st.Page("views/players.py", title=t("nav.players")),
    st.Page("views/regret.py", title=t("nav.regret")),
    st.Page("views/market.py", title=t("nav.market")),
]
pg = st.navigation(pages)
pg.run()

# Rendered last → sits at the bottom of the sidebar, below the page's own
# selectors, always visible.
render_language_toggle()
