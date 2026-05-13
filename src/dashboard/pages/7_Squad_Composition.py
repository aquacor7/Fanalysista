"""Where a team's points come from — visual breakdown of squad contribution.

Three views of the same underlying data (gold/player_season.csv):
    1. Stacked vertical bar — each player's total_fv split into active vs missed.
    2. Sunburst (pie-of-pie) — inner ring = position, outer = player.
    3. Donut — player share of the team's total_active_fv.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_player_season, require_data

# Italian football position colours
POSITION_COLOR = {
    "P": "#FFC107",  # gold     — Portiere
    "D": "#1E88E5",  # blue     — Difensore
    "C": "#43A047",  # green    — Centrocampista
    "A": "#E53935",  # red      — Attaccante
}
POSITION_ORDER = ["P", "D", "C", "A"]

st.set_page_config(page_title="Squad Composition", layout="wide")
st.title("Squad Composition")

league, comp = require_data()
ps = load_player_season(league, comp)

# ---- sidebar ----
teams = sorted(ps.team.unique())
sel_team = st.sidebar.selectbox("Focus team", teams)
sort_mode = st.sidebar.radio(
    "Sort players by",
    options=["Total FV (active + missed)", "Active FV", "Missed FV", "Position then name"],
    index=0,
)
min_total_fv = st.sidebar.slider(
    "Hide players below this total FV",
    min_value=0.0,
    max_value=float(ps.total_fv.max()),
    value=0.0,
    step=5.0,
)

team_ps = ps[(ps.team == sel_team) & (ps.total_fv >= min_total_fv)].copy()

if sort_mode == "Active FV":
    team_ps = team_ps.sort_values("total_active_fv", ascending=False)
elif sort_mode == "Missed FV":
    team_ps = team_ps.sort_values("total_fv_missed", ascending=False)
elif sort_mode == "Position then name":
    team_ps["_o"] = team_ps.position.map({p: i for i, p in enumerate(POSITION_ORDER)})
    team_ps = team_ps.sort_values(["_o", "player"]).drop(columns="_o")
else:
    team_ps = team_ps.sort_values("total_fv", ascending=False)

# ---- KPIs ----
total_active = float(team_ps.total_active_fv.sum())
total_missed = float(team_ps.total_fv_missed.sum())
captureable = total_active + total_missed
c1, c2, c3, c4 = st.columns(4)
c1.metric("Squad size (rotation)", int(team_ps.player.nunique()))
c2.metric("Total active FV", f"{total_active:.1f}")
c3.metric("Total FV missed", f"{total_missed:.1f}")
c4.metric(
    "Capture rate",
    f"{(total_active / captureable * 100):.1f}%" if captureable else "—",
)

st.divider()

# ---- 1. Stacked vertical bar ----
st.subheader(f"{sel_team} — total FV per player (active + missed)")
fig_bar = go.Figure(data=[
    go.Bar(
        name="Active (counted)",
        x=team_ps.player,
        y=team_ps.total_active_fv,
        marker_color="#2E7D32",
        customdata=team_ps[["position", "apps_active"]],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Position: %{customdata[0]}<br>"
            "Active FV: %{y:.1f}<br>"
            "Active apps: %{customdata[1]}<extra></extra>"
        ),
    ),
    go.Bar(
        name="Missed (on bench)",
        x=team_ps.player,
        y=team_ps.total_fv_missed,
        marker_color="#EF6C00",
        customdata=team_ps[["position", "apps_missed"]],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Position: %{customdata[0]}<br>"
            "Missed FV: %{y:.1f}<br>"
            "Missed apps: %{customdata[1]}<extra></extra>"
        ),
    ),
])
fig_bar.update_layout(
    barmode="stack",
    xaxis_tickangle=-45,
    yaxis_title="Fantavoto",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=550,
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig_bar, width="stretch")
st.caption(
    "Green = contribution to your TOTALE. Orange = the player got a voto but you "
    "didn't play them. A tall orange segment = a star you under-used."
)

# ---- 2. Sunburst: position -> player ----
st.subheader("Pie of pie — position then player share of active FV")
sun_df = team_ps[team_ps.total_active_fv > 0].copy()
fig_sun = px.sunburst(
    sun_df,
    path=["position", "player"],
    values="total_active_fv",
    color="position",
    color_discrete_map=POSITION_COLOR,
    branchvalues="total",
)
fig_sun.update_traces(
    textinfo="label+percent parent",
    hovertemplate="<b>%{label}</b><br>Active FV: %{value:.1f}<br>"
                  "%{percentParent:.1%} of segment<extra></extra>",
)
fig_sun.update_layout(height=600, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig_sun, width="stretch")
st.caption(
    "Inner ring: each position's share of your TOTALE-relevant points. "
    "Outer ring: individual players within that position. "
    "Click a position to zoom in."
)

# ---- 3. Donut: player share of active FV ----
with st.expander("Single-ring donut (player only)"):
    donut_df = team_ps[team_ps.total_active_fv > 0].copy()
    fig_donut = px.pie(
        donut_df,
        names="player",
        values="total_active_fv",
        color="position",
        color_discrete_map=POSITION_COLOR,
        hole=0.45,
    )
    fig_donut.update_traces(
        textposition="inside",
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Active FV: %{value:.1f}<br>"
                      "Share: %{percent}<extra></extra>",
    )
    fig_donut.update_layout(height=550, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_donut, width="stretch")

# ---- Raw table (collapsed by default) ----
with st.expander("Player table"):
    st.dataframe(
        team_ps[[
            "position", "player", "apps_active", "apps_missed",
            "total_active_fv", "total_fv_missed", "total_fv",
            "pct_fv_captured", "avg_active_fv",
        ]],
        width="stretch",
        hide_index=True,
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
