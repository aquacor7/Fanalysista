"""Player-season explorer with team/position/min-apps filters.

Clicking a player row opens Player Detail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import streamlit as st

from data import load_player_season, require_data
from theme import POSITION_COLOR, POSITION_ORDER

st.set_page_config(page_title="Players", layout="wide")
st.title("Players")

league, comp = require_data()
ps = load_player_season(league, comp)

# ---- filters ----
teams = sorted(ps.team.unique())
sel_teams = st.sidebar.multiselect("Team", teams, default=teams)
sel_pos = st.sidebar.multiselect("Position", POSITION_ORDER, default=POSITION_ORDER)

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
].sort_values(sort_col, ascending=False).reset_index(drop=True)

st.markdown(f"**{len(filtered)} players** match filters — click a row to open Player Detail")

# ---- table (clickable) ----
event = st.dataframe(
    filtered,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="pl_select",
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
if event.selection.rows:
    row = filtered.iloc[event.selection.rows[0]]
    st.session_state.selected_team = row.team
    st.session_state.selected_player = row.player
    st.switch_page("pages/3_Player_Detail.py")

# ---- scatter: capture rate vs total active fv (positions in standard colour) ----
st.subheader("Capture rate vs total active FV")
chart_df = filtered.dropna(subset=["pct_fv_captured", "total_active_fv"]).copy()
chart_df["capture_pct"] = (chart_df["pct_fv_captured"] * 100).round(1)
fig = px.scatter(
    chart_df,
    x="capture_pct", y="total_active_fv",
    color="position", size="apps_active",
    color_discrete_map=POSITION_COLOR,
    category_orders={"position": POSITION_ORDER},
    hover_data={"team": True, "player": True, "apps_active": True, "apps_missed": True},
    labels={"capture_pct": "% FV captured", "total_active_fv": "Total active FV"},
)
fig.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")
st.caption(
    "Top-right = high contribution AND high efficiency. "
    "Top-left = scored a lot but you missed a lot too (high-regret player). "
    "Hover to identify; use filters to narrow."
)
