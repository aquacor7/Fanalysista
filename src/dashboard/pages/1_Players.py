"""Player-season explorer with team/position/min-apps filters."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from data import load_player_season, require_data

st.set_page_config(page_title="Players", layout="wide")
st.title("Players")

league, comp = require_data()
ps = load_player_season(league, comp)

# ---- filters ----
teams = sorted(ps.team.unique())
sel_teams = st.sidebar.multiselect("Team", teams, default=teams)

positions = ["P", "D", "C", "A"]
sel_pos = st.sidebar.multiselect("Position", positions, default=positions)

max_squad = int(ps.apps_in_squad.max())
min_apps = st.sidebar.slider("Min apps in squad", 0, max_squad, 0)

sort_options = [
    "total_active_fv", "avg_active_fv", "pct_fv_captured", "pct_active_rate",
    "apps_active", "apps_missed", "total_fv_missed", "avg_fv_missed",
    "best_active_fv", "total_voto", "total_fv",
]
sort_col = st.sidebar.selectbox("Sort by", sort_options, index=0)

filtered = ps[
    ps.team.isin(sel_teams)
    & ps.position.isin(sel_pos)
    & (ps.apps_in_squad >= min_apps)
].sort_values(sort_col, ascending=False)

st.markdown(f"**{len(filtered)} players** match filters")

# ---- table ----
st.dataframe(
    filtered,
    width="stretch",
    hide_index=True,
    column_config={
        "pct_fv_captured": st.column_config.ProgressColumn(
            "% FV captured", min_value=0.0, max_value=1.0, format="percent",
        ),
        "pct_active_rate": st.column_config.ProgressColumn(
            "% Active rate", min_value=0.0, max_value=1.0, format="percent",
        ),
        "total_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "avg_active_fv": st.column_config.NumberColumn(format="%.2f"),
        "total_fv_missed": st.column_config.NumberColumn(format="%.1f"),
        "avg_fv_missed": st.column_config.NumberColumn(format="%.2f"),
        "best_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "worst_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "total_voto": st.column_config.NumberColumn(format="%.1f"),
        "total_fv": st.column_config.NumberColumn(format="%.1f"),
    },
)

# ---- scatter: capture rate vs total active fv ----
st.subheader("Capture rate vs total active FV")
chart_df = filtered.dropna(subset=["pct_fv_captured", "total_active_fv"]).copy()
chart_df["capture_pct"] = (chart_df["pct_fv_captured"] * 100).round(1)
st.scatter_chart(
    chart_df,
    x="capture_pct",
    y="total_active_fv",
    color="position",
    size="apps_active",
    height=450,
)
st.caption(
    "Top-right = high contribution AND high efficiency. "
    "Top-left = scored a lot but you missed a lot too (high-regret player). "
    "Hover to identify; use filters to narrow."
)
