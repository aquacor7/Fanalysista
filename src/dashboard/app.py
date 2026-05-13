"""Fantacalcio Analytics — home page.

Run from the project root:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from data import (
    load_matches,
    load_player_season,
    load_team_season,
    require_data,
)

st.set_page_config(page_title="Fantacalcio Analytics", layout="wide")
st.title("Fantacalcio Analytics")

league, comp = require_data()
ts = load_team_season(league, comp)
ps = load_player_season(league, comp)
mt = load_matches(league, comp)

# ---- KPIs ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Teams", len(ts))
c2.metric("Giornate", int(mt.giornata.nunique()))
c3.metric("Matches", len(mt) // 2)
c4.metric("Players tracked", int(ps.player.nunique()))

st.divider()

# ---- League table (compact) ----
st.subheader("League table")
st.dataframe(
    ts,
    width="stretch",
    hide_index=True,
    column_config={
        "points": st.column_config.NumberColumn("Pts", format="%d"),
        "goals_for": st.column_config.NumberColumn("GF", format="%d"),
        "goals_against": st.column_config.NumberColumn("GA", format="%d"),
        "goal_diff": st.column_config.NumberColumn("GD", format="%d"),
        "totale_avg": st.column_config.NumberColumn("Avg TOT", format="%.2f"),
        "totale_max": st.column_config.NumberColumn("Max TOT", format="%.1f"),
        "totale_min": st.column_config.NumberColumn("Min TOT", format="%.1f"),
        "opp_totale_avg": st.column_config.NumberColumn("Opp avg", format="%.2f"),
        "totale_diff_avg": st.column_config.NumberColumn("Diff avg", format="%+.2f"),
    },
)

# ---- Top performers across competition ----
st.subheader("Top 10 contributors (any team) — click a row to open Player Detail")
top = ps.sort_values("total_active_fv", ascending=False).head(10).reset_index(drop=True)
event_home = st.dataframe(
    top[[
        "team", "position", "player", "apps_active", "total_active_fv",
        "avg_active_fv", "pct_fv_captured", "best_active_fv",
    ]],
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="home_top_select",
    column_config={
        "pct_fv_captured": st.column_config.ProgressColumn(
            "% FV captured", min_value=0.0, max_value=1.0, format="percent",
        ),
        "total_active_fv": st.column_config.NumberColumn("Total active fv", format="%.1f"),
        "avg_active_fv": st.column_config.NumberColumn("Avg / game", format="%.2f"),
        "best_active_fv": st.column_config.NumberColumn("Best game", format="%.1f"),
    },
)
if event_home.selection.rows:
    row = top.iloc[event_home.selection.rows[0]]
    from modals import maybe_open_player_modal
    maybe_open_player_modal(league, comp, row.team, row.player)

st.caption(
    "**Pages:** League Table → Team Detail → Player Detail (drill-in hierarchy). "
    "Players and Regret are cross-team comparison views. "
    "Click any team or player to open a summary modal — escalate to the full page from there."
)
