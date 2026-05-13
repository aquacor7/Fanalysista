"""Per-team schedule + giornata-by-giornata TOTALE trend."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from data import load_matches, require_data

st.set_page_config(page_title="Schedule", layout="wide")
st.title("Schedule")

league, comp = require_data()
mt = load_matches(league, comp)

# Attach opponent totale via self-join
opp = mt[["giornata", "team", "totale"]].rename(
    columns={"team": "opponent", "totale": "opp_totale"}
)
mt = mt.merge(opp, on=["giornata", "opponent"], how="left")

teams = sorted(mt.team.unique())
sel_team = st.sidebar.selectbox("Team", teams)

view = mt[mt.team == sel_team].sort_values("giornata")
view = view[[
    "giornata", "opponent", "side", "result",
    "score_for", "score_against", "totale", "opp_totale", "module",
]]

# Header KPIs
wins = int((view.result == "W").sum())
draws = int((view.result == "D").sum())
losses = int((view.result == "L").sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Played", len(view))
c2.metric("W / D / L", f"{wins}-{draws}-{losses}")
c3.metric("Avg TOTALE", f"{view.totale.mean():.2f}")
c4.metric("Avg opp", f"{view.opp_totale.mean():.2f}")

# Schedule table
st.subheader(f"{sel_team} — schedule")
st.dataframe(
    view,
    width="stretch",
    hide_index=True,
    column_config={
        "totale": st.column_config.NumberColumn(format="%.1f"),
        "opp_totale": st.column_config.NumberColumn(format="%.1f"),
        "score_for": st.column_config.NumberColumn("GF", format="%d"),
        "score_against": st.column_config.NumberColumn("GA", format="%d"),
    },
)

# TOTALE trend
st.subheader("TOTALE over time")
st.line_chart(view.set_index("giornata")[["totale", "opp_totale"]], height=400)
