"""League table — the season at a glance.

Includes:
    - the table (clickable: pick a team to drill into Team Detail)
    - points bar
    - dumbbell chart of team_avg vs opp_avg
    - per-team single-giornata peak
    - TOTALE heatmap (teams × giornate)
    - cumulative standings race (points and TOTALE)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import load_matches, load_team_season, require_data
from modals import maybe_open_team_modal
from theme import OPPONENT_COLOR, SUBJECT_COLOR

st.set_page_config(page_title="League Table", layout="wide")
st.title("League Table")

league, comp = require_data()
ts = load_team_season(league, comp)

# ---- league table (clickable: opens team summary modal) ----
st.markdown("**Click any team row for a summary** (the modal has an Open full page button).")
event_lt = st.dataframe(
    ts,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="lt_select",
    column_config={
        "points": st.column_config.NumberColumn("Pts", format="%d"),
        "goal_diff": st.column_config.NumberColumn("GD", format="%+d"),
        "totale_avg": st.column_config.NumberColumn(format="%.2f"),
        "opp_totale_avg": st.column_config.NumberColumn(format="%.2f"),
        "totale_diff_avg": st.column_config.NumberColumn(format="%+.2f"),
    },
)
if event_lt.selection.rows:
    maybe_open_team_modal(league, comp, ts.iloc[event_lt.selection.rows[0]].team, key="lt_select")

# ---- points bar (clickable: opens team summary modal) ----
st.subheader("Points — click any bar for a team summary")
pts_df = ts[["team", "points"]].copy()
fig_pts = px.bar(
    pts_df, x="team", y="points",
    custom_data=["team"],
    color_discrete_sequence=[SUBJECT_COLOR],
)
fig_pts.update_traces(
    hovertemplate="<b>%{x}</b><br>Points: %{y}<extra></extra>",
)
fig_pts.update_layout(
    height=400, xaxis_tickangle=-45, yaxis_title="Points", xaxis_title="",
    margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
    clickmode="event+select",
)
event_pts = st.plotly_chart(
    fig_pts, width="stretch",
    on_select="rerun", selection_mode="points",
    key="lt_points_bar_select",
)
if event_pts.selection and event_pts.selection.points:
    p = event_pts.selection.points[0]
    cd = p.get("customdata") or []
    clicked_team = cd[0] if cd else p.get("x")
    if clicked_team:
        maybe_open_team_modal(league, comp, clicked_team, key="lt_points_bar_select")

# ---- dumbbell chart: team_avg vs opp_avg, sorted by team_avg ----
st.subheader("Average TOTALE — team vs opponents")
dumbbell = ts[["team", "totale_avg", "opp_totale_avg"]].sort_values(
    "totale_avg", ascending=True  # so highest is at the top of the chart
)
fig_db = go.Figure()
# connector lines first (so dots sit on top)
for _, row in dumbbell.iterrows():
    fig_db.add_trace(go.Scatter(
        x=[row.opp_totale_avg, row.totale_avg],
        y=[row.team, row.team],
        mode="lines",
        line=dict(color="#CCCCCC", width=2),
        hoverinfo="skip",
        showlegend=False,
    ))
fig_db.add_trace(go.Scatter(
    x=dumbbell.opp_totale_avg, y=dumbbell.team,
    mode="markers",
    marker=dict(size=13, color=OPPONENT_COLOR, line=dict(color="white", width=1)),
    name="Opponent avg",
    hovertemplate="<b>%{y}</b><br>Opp avg: %{x:.2f}<extra></extra>",
))
fig_db.add_trace(go.Scatter(
    x=dumbbell.totale_avg, y=dumbbell.team,
    mode="markers",
    marker=dict(size=13, color=SUBJECT_COLOR, line=dict(color="white", width=1)),
    name="Team avg",
    hovertemplate="<b>%{y}</b><br>Team avg: %{x:.2f}<extra></extra>",
))
fig_db.update_layout(
    height=450, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="Average TOTALE", yaxis_title="",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
event_db = st.plotly_chart(
    fig_db, width="stretch",
    on_select="rerun", selection_mode="points",
    key="lt_dumbbell_select",
)
if event_db.selection and event_db.selection.points:
    p = event_db.selection.points[0]
    clicked_team = p.get("y")  # team name lives on the y axis
    if clicked_team:
        maybe_open_team_modal(league, comp, clicked_team, key="lt_dumbbell_select")
st.caption(
    "Each row: one team. Blue dot = the team's own avg TOTALE. "
    "Red dot = avg TOTALE their opponents put up against them. "
    "The longer the line, the bigger the gap. Click any dot to open that team's summary."
)

# ---- per-team peak ----
st.subheader("Best single-giornata TOTALE per team")
best = ts[["team", "totale_max", "totale_max_g", "totale_max_vs"]].sort_values(
    "totale_max", ascending=False
)
st.dataframe(best, width="stretch", hide_index=True)

# ---- TOTALE heatmap across giornate ----
st.subheader("TOTALE heatmap — teams × giornate")
mt = load_matches(league, comp)
pivot = mt.pivot(index="team", columns="giornata", values="totale")
pivot = pivot.reindex(ts.team)
fig_hm = px.imshow(
    pivot,
    color_continuous_scale="RdYlGn",
    aspect="auto",
    labels=dict(x="Giornata", y="Team", color="TOTALE"),
    text_auto=".0f",
)
fig_hm.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
fig_hm.update_xaxes(side="top", dtick=1)
st.plotly_chart(fig_hm, width="stretch")
st.caption(
    "Green = high-scoring giornata, red = low. Read horizontally to see a team's "
    "consistency; vertically to see which giornate had league-wide explosions."
)

# ---- Cumulative standings race ----
st.subheader("Standings race — cumulative through the season")
mt_sorted = mt.sort_values(["team", "giornata"]).copy()
mt_sorted["match_pts"] = mt_sorted.result.map({"W": 3, "D": 1, "L": 0}).fillna(0)
mt_sorted["cum_pts"] = mt_sorted.groupby("team")["match_pts"].cumsum()
mt_sorted["cum_totale"] = mt_sorted.groupby("team")["totale"].cumsum()
team_order = ts.team.tolist()

tab_pts, tab_tot = st.tabs(["Competition points", "Cumulative TOTALE"])
with tab_pts:
    fig_race_p = px.line(
        mt_sorted, x="giornata", y="cum_pts", color="team",
        category_orders={"team": team_order}, markers=True,
        labels={"cum_pts": "Cumulative points", "giornata": "Giornata"},
    )
    fig_race_p.update_layout(height=520, hovermode="x unified",
                             margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_race_p, width="stretch")
    st.caption(
        "Standings race — 3 points per win, 1 per draw. "
        "Click a team in the legend to isolate; double-click to toggle others off."
    )
with tab_tot:
    fig_race_t = px.line(
        mt_sorted, x="giornata", y="cum_totale", color="team",
        category_orders={"team": team_order}, markers=False,
        labels={"cum_totale": "Cumulative TOTALE", "giornata": "Giornata"},
    )
    fig_race_t.update_layout(height=520, hovermode="x unified",
                             margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_race_t, width="stretch")
    st.caption(
        "Raw fantasy scoring over time. Steeper slope = more fv produced each giornata."
    )
