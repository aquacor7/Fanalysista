"""Full league table with bar charts for points and TOTALE comparison."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from data import load_matches, load_team_season, require_data

st.set_page_config(page_title="League Table", layout="wide")
st.title("League Table")

league, comp = require_data()
ts = load_team_season(league, comp)

# ---- league table ----
st.dataframe(
    ts,
    width="stretch",
    hide_index=True,
    column_config={
        "points": st.column_config.NumberColumn("Pts", format="%d"),
        "goal_diff": st.column_config.NumberColumn("GD", format="%+d"),
        "totale_avg": st.column_config.NumberColumn(format="%.2f"),
        "opp_totale_avg": st.column_config.NumberColumn(format="%.2f"),
        "totale_diff_avg": st.column_config.NumberColumn(format="%+.2f"),
    },
)

# ---- points bar ----
st.subheader("Points")
st.bar_chart(ts.set_index("team")["points"], height=400)

# ---- avg totale: own vs opponent ----
st.subheader("Average TOTALE — team vs opponents")
cmp = (
    ts.set_index("team")[["totale_avg", "opp_totale_avg"]]
      .rename(columns={"totale_avg": "team_avg", "opp_totale_avg": "opp_avg"})
)
st.bar_chart(cmp, height=400)

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
# Order rows by points-driven team_season order so the heatmap reads like the table
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

# Order teams in legend by final standing for readability
team_order = ts.team.tolist()  # already sorted by points

tab_pts, tab_tot = st.tabs(["Competition points", "Cumulative TOTALE"])

with tab_pts:
    fig_race_p = px.line(
        mt_sorted, x="giornata", y="cum_pts", color="team",
        category_orders={"team": team_order},
        markers=True,
        labels={"cum_pts": "Cumulative points", "giornata": "Giornata"},
    )
    fig_race_p.update_layout(height=520, hovermode="x unified",
                             margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_race_p, width="stretch")
    st.caption(
        "The actual standings race — 3 points per win, 1 per draw. "
        "Click a team in the legend to isolate; double-click to toggle others off."
    )

with tab_tot:
    fig_race_t = px.line(
        mt_sorted, x="giornata", y="cum_totale", color="team",
        category_orders={"team": team_order},
        markers=False,
        labels={"cum_totale": "Cumulative TOTALE", "giornata": "Giornata"},
    )
    fig_race_t.update_layout(height=520, hovermode="x unified",
                             margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_race_t, width="stretch")
    st.caption(
        "Raw fantasy scoring over time. The slope shows a team's average per-game "
        "production — a steeper line means more fv produced each giornata."
    )
