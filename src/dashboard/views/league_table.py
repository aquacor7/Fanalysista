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

import i18n
from data import load_matches, load_team_season, require_data
from i18n import t
from modals import maybe_open_team_modal
from theme import OPPONENT_COLOR, SUBJECT_COLOR


league, comp = require_data()
st.title(t("league_table.title"))
ts = load_team_season(league, comp)

# ---- league table (clickable: opens team summary modal) ----
st.markdown(t("league_table.click_hint"))
event_lt = st.dataframe(
    ts,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="lt_select",
    column_config=i18n.columns_config(
        ts,
        formats={
            "points": "%d", "goal_diff": "%+d", "totale_sum": "%.1f",
            "totale_avg": "%.2f", "totale_max": "%.1f", "totale_min": "%.1f",
            "opp_totale_avg": "%.2f", "totale_diff_avg": "%+.2f",
            "regret_total": "%.1f", "regret_avg": "%.2f", "regret_max": "%.1f",
            "modificatore_difesa_sum": "%.1f",
        },
    ),
)
if event_lt.selection.rows:
    maybe_open_team_modal(league, comp, ts.iloc[event_lt.selection.rows[0]].team, key="lt_select")

# ---- points bar (clickable: opens team summary modal) ----
st.subheader(t("league_table.points_header"))
pts_df = ts[["team", "points"]].copy()
fig_pts = px.bar(
    pts_df, x="team", y="points",
    custom_data=["team"],
    color_discrete_sequence=[SUBJECT_COLOR],
)
fig_pts.update_traces(
    hovertemplate="<b>%{x}</b><br>" + t("league_table.points_axis") + ": %{y}<extra></extra>",
)
fig_pts.update_layout(
    height=400, xaxis_tickangle=-45, yaxis_title=t("league_table.points_axis"), xaxis_title="",
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
st.subheader(t("league_table.dumbbell_header"))
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
    name=t("league_table.dumbbell_opp"),
    hovertemplate="<b>%{y}</b><br>" + t("league_table.dumbbell_opp") + ": %{x:.2f}<extra></extra>",
))
fig_db.add_trace(go.Scatter(
    x=dumbbell.totale_avg, y=dumbbell.team,
    mode="markers",
    marker=dict(size=13, color=SUBJECT_COLOR, line=dict(color="white", width=1)),
    name=t("league_table.dumbbell_team"),
    hovertemplate="<b>%{y}</b><br>" + t("league_table.dumbbell_team") + ": %{x:.2f}<extra></extra>",
))
fig_db.update_layout(
    height=450, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title=t("league_table.dumbbell_axis"), yaxis_title="",
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
st.caption(t("league_table.dumbbell_caption"))

# ---- per-team peak ----
st.subheader(t("league_table.peak_header"))
best = ts[["team", "totale_max", "totale_max_g", "totale_max_vs"]].sort_values(
    "totale_max", ascending=False
)
st.dataframe(best, width="stretch", hide_index=True,
             column_config=i18n.columns_config(best, formats={"totale_max": "%.1f"}))

# ---- TOTALE heatmap across giornate ----
st.subheader(t("league_table.heatmap_header"))
mt = load_matches(league, comp)
pivot = mt.pivot(index="team", columns="giornata", values="totale")
pivot = pivot.reindex(ts.team)
fig_hm = px.imshow(
    pivot,
    color_continuous_scale="RdYlGn",
    aspect="auto",
    labels=dict(x=i18n.col("giornata"), y=i18n.col("team"), color=i18n.col("totale")),
    text_auto=".0f",
)
fig_hm.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
fig_hm.update_xaxes(side="top", dtick=1)
st.plotly_chart(fig_hm, width="stretch")
st.caption(t("league_table.heatmap_caption"))

# ---- Cumulative standings race ----
st.subheader(t("league_table.race_header"))
mt_sorted = mt.sort_values(["team", "giornata"]).copy()
mt_sorted["match_pts"] = mt_sorted.result.map({"W": 3, "D": 1, "L": 0}).fillna(0)
mt_sorted["cum_pts"] = mt_sorted.groupby("team")["match_pts"].cumsum()
mt_sorted["cum_totale"] = mt_sorted.groupby("team")["totale"].cumsum()
team_order = ts.team.tolist()

tab_pts, tab_tot = st.tabs([t("league_table.race_tab_points"), t("league_table.race_tab_totale")])
with tab_pts:
    fig_race_p = px.line(
        mt_sorted, x="giornata", y="cum_pts", color="team",
        category_orders={"team": team_order}, markers=True,
        labels={"cum_pts": t("league_table.race_points_axis"), "giornata": i18n.col("giornata")},
    )
    fig_race_p.update_layout(height=520, hovermode="x unified",
                             margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_race_p, width="stretch")
    st.caption(t("league_table.race_points_caption"))
with tab_tot:
    fig_race_t = px.line(
        mt_sorted, x="giornata", y="cum_totale", color="team",
        category_orders={"team": team_order}, markers=False,
        labels={"cum_totale": t("league_table.race_totale_axis"), "giornata": i18n.col("giornata")},
    )
    fig_race_t.update_layout(height=520, hovermode="x unified",
                             margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_race_t, width="stretch")
    st.caption(t("league_table.race_totale_caption"))
