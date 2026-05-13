"""Single-team drill-in.

Three sections:
    1. Header / season KPIs (record, points, totale stats, regret)
    2. Schedule (match log + TOTALE vs opponent line chart)
    3. Squad composition (stacked bar per player + sunburst position→player)

This page is the natural target when a team name is clicked from anywhere
in the dashboard (League Table, Players, …). It reads from session_state's
`selected_team` so navigation persists across pages.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_matches, load_player_season, load_team_season, require_data
from theme import (
    ACTIVE_COLOR,
    MISSED_COLOR,
    OPPONENT_COLOR,
    POSITION_COLOR,
    POSITION_ORDER,
    SUBJECT_COLOR,
)

st.set_page_config(page_title="Team Detail", layout="wide")

league, comp = require_data()
mt = load_matches(league, comp)
ps = load_player_season(league, comp)
ts = load_team_season(league, comp)

# ---- sidebar team picker (shared selected_team across pages) ----
teams = sorted(mt.team.unique())
default = st.session_state.get("selected_team")
if default not in teams:
    default = teams[0]
sel_team = st.sidebar.selectbox(
    "Team", teams, index=teams.index(default), key="td_team_box",
)
st.session_state.selected_team = sel_team

st.title(sel_team)

# ---- season KPI row ----
team_row = ts[ts.team == sel_team].iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("W / D / L", f"{int(team_row.wins)} / {int(team_row.draws)} / {int(team_row.losses)}")
c2.metric("Points", int(team_row.points))
c3.metric("Avg TOTALE", f"{team_row.totale_avg:.2f}")
c4.metric("Goal diff", f"{int(team_row.goal_diff):+d}")
if "regret_total" in ts.columns and pd.notna(team_row.get("regret_total")):
    c5.metric(
        "Regret total",
        f"{team_row.regret_total:.1f}",
        delta=f"{int(team_row.get('perfect_giornate', 0))} perfect g",
        delta_color="off",
    )

st.divider()

# ============================================================
# 1. Schedule
# ============================================================
st.subheader("Schedule")

opp = mt[["giornata", "team", "totale"]].rename(
    columns={"team": "opponent", "totale": "opp_totale"})
schedule = (mt[mt.team == sel_team]
              .merge(opp, on=["giornata", "opponent"], how="left")
              .sort_values("giornata"))
view = schedule[[
    "giornata", "opponent", "side", "result",
    "score_for", "score_against", "totale", "opp_totale", "module",
]]
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

st.markdown("**TOTALE over time — team vs opponent**")
trend_df = (
    schedule[["giornata", "totale", "opp_totale"]]
      .melt(id_vars="giornata", var_name="who", value_name="value")
)
trend_df["who"] = trend_df["who"].map({"totale": sel_team, "opp_totale": "Opponent"})

fig_trend = px.line(
    trend_df, x="giornata", y="value", color="who", markers=True,
    color_discrete_map={sel_team: SUBJECT_COLOR, "Opponent": OPPONENT_COLOR},
    labels={"value": "TOTALE", "giornata": "Giornata", "who": ""},
)
fig_trend.update_layout(
    height=380, hovermode="x unified",
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_trend, width="stretch")
st.caption(
    f"Dark blue = {sel_team}'s TOTALE. Red = opponent's TOTALE that giornata."
)

st.divider()

# ============================================================
# 2. Squad composition
# ============================================================
st.subheader("Squad composition")

team_ps = ps[ps.team == sel_team].copy()

sort_mode = st.radio(
    "Sort players by",
    ["Total FV (active + missed)", "Active FV", "Missed FV", "Position then name"],
    horizontal=True, index=0,
)
if sort_mode == "Active FV":
    team_ps = team_ps.sort_values("total_active_fv", ascending=False)
elif sort_mode == "Missed FV":
    team_ps = team_ps.sort_values("total_fv_missed", ascending=False)
elif sort_mode == "Position then name":
    team_ps["_o"] = team_ps.position.map({p: i for i, p in enumerate(POSITION_ORDER)})
    team_ps = team_ps.sort_values(["_o", "player"]).drop(columns="_o")
else:
    team_ps = team_ps.sort_values("total_fv", ascending=False)

# ---- stacked bar: per-player active + missed ----
st.markdown("**Total FV per player — captured (green) vs missed (orange)**")
fig_bar = go.Figure(data=[
    go.Bar(
        name="Captured (active)", x=team_ps.player, y=team_ps.total_active_fv,
        marker_color=ACTIVE_COLOR,
        customdata=team_ps[["position", "apps_active"]],
        hovertemplate=("<b>%{x}</b><br>Position: %{customdata[0]}<br>"
                       "Active FV: %{y:.1f}<br>"
                       "Active apps: %{customdata[1]}<extra></extra>"),
    ),
    go.Bar(
        name="Missed (on bench)", x=team_ps.player, y=team_ps.total_fv_missed,
        marker_color=MISSED_COLOR,
        customdata=team_ps[["position", "apps_missed"]],
        hovertemplate=("<b>%{x}</b><br>Position: %{customdata[0]}<br>"
                       "Missed FV: %{y:.1f}<br>"
                       "Missed apps: %{customdata[1]}<extra></extra>"),
    ),
])
fig_bar.update_layout(
    barmode="stack", xaxis_tickangle=-45, yaxis_title="Fantavoto",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=520, margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig_bar, width="stretch")

# ---- sunburst position -> player ----
st.markdown("**Pie of pie — position, then player share of active FV**")
sun_df = team_ps[team_ps.total_active_fv > 0]
fig_sun = px.sunburst(
    sun_df, path=["position", "player"], values="total_active_fv",
    color="position", color_discrete_map=POSITION_COLOR, branchvalues="total",
)
fig_sun.update_traces(
    textinfo="label+percent parent",
    hovertemplate="<b>%{label}</b><br>Active FV: %{value:.1f}<br>"
                  "%{percentParent:.1%} of segment<extra></extra>",
)
fig_sun.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_sun, width="stretch")
st.caption("Click a position slice in the sunburst to zoom in.")

# ---- clickable player table ----
st.markdown("**Click a player to open their Detail page**")
player_table = team_ps[[
    "position", "player", "apps_active", "apps_missed",
    "total_active_fv", "total_fv_missed", "total_fv",
    "pct_fv_captured", "avg_active_fv",
]]
event = st.dataframe(
    player_table,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="td_player_select",
    column_config={
        "pct_fv_captured": st.column_config.ProgressColumn(
            "% captured", min_value=0.0, max_value=1.0, format="percent",
        ),
        "total_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "total_fv_missed": st.column_config.NumberColumn(format="%.1f"),
        "total_fv": st.column_config.NumberColumn(format="%.1f"),
        "avg_active_fv": st.column_config.NumberColumn(format="%.2f"),
    },
)
if event.selection.rows:
    selected = player_table.iloc[event.selection.rows[0]]
    st.session_state.selected_team = sel_team
    st.session_state.selected_player = selected.player
    st.switch_page("pages/3_Player_Detail.py")
