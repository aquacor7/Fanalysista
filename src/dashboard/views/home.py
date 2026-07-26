"""Fantacalcio Analytics — home page (run via the app.py router)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from data import (
    load_matches,
    load_player_season,
    load_team_season,
    require_data,
)
import i18n
from i18n import t
from modals import maybe_open_player_modal, maybe_open_team_modal

league, comp = require_data()
st.title(t("app.title"))
ts = load_team_season(league, comp)
ps = load_player_season(league, comp)
mt = load_matches(league, comp)

# ---- KPIs ----
c1, c2, c3, c4 = st.columns(4)
c1.metric(t("common.teams"), len(ts))
c2.metric(t("common.giornate"), int(mt.giornata.nunique()))
c3.metric(t("common.matches"), len(mt) // 2)
c4.metric(t("common.players_tracked"), int(ps.player.nunique()))

st.divider()

# ---- League table (clickable: opens team summary modal) ----
st.subheader(t("home.league_table_header"))
event_home_lt = st.dataframe(
    ts,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="home_lt_select",
    column_config=i18n.columns_config(
        ts,
        formats={
            "points": "%d", "goals_for": "%d", "goals_against": "%d",
            "goal_diff": "%d", "totale_sum": "%.1f", "totale_avg": "%.2f",
            "totale_max": "%.1f", "totale_min": "%.1f", "opp_totale_avg": "%.2f",
            "totale_diff_avg": "%+.2f", "regret_total": "%.1f", "regret_avg": "%.2f",
            "regret_max": "%.1f", "modificatore_difesa_sum": "%.1f",
        },
    ),
)
if event_home_lt.selection.rows:
    maybe_open_team_modal(league, comp, ts.iloc[event_home_lt.selection.rows[0]].team, key="home_lt_select")

# ---- Top performers across competition ----
st.subheader(t("home.top_contributors_header"))
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
    column_config=i18n.columns_config(
        top[["team", "position", "player", "apps_active", "total_active_fv",
             "avg_active_fv", "pct_fv_captured", "best_active_fv"]],
        formats={"total_active_fv": "%.1f", "avg_active_fv": "%.2f",
                 "best_active_fv": "%.1f"},
        progress={"pct_fv_captured"},
    ),
)
if event_home.selection.rows:
    row = top.iloc[event_home.selection.rows[0]]
    maybe_open_player_modal(league, comp, row.team, row.player, key="home_top_select")

st.caption(t("home.pages_caption"))
