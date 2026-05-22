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
import streamlit as st

from data import (
    load_matches,
    load_player_season,
    load_team_season,
    persist_sidebar_selectbox,
    require_data,
)
from modals import maybe_open_player_modal
from ui import breadcrumbs
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

# ---- sidebar team picker (persists across nav via canonical key) ----
teams = sorted(mt.team.unique())
sel_team = persist_sidebar_selectbox(
    "Team", teams, widget_key="selected_team", canon_key="_canon_team",
)

breadcrumbs(
    ("League Table", "pages/1_League_Table.py"),
    (sel_team, None),
)
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
        "side": st.column_config.TextColumn("Side"),
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

# ---- stacked bar: per-player active + missed (clickable) ----
st.markdown("**Total FV per player — captured (green) vs missed (orange).** "
            "Click any bar to open that player's summary.")
# Long-format dataframe so px.bar attaches per-row customdata identically across
# both stacked traces — makes click→player extraction robust regardless of which
# segment the user clicked.
bar_long = team_ps.melt(
    id_vars=["player", "position", "apps_active", "apps_missed"],
    value_vars=["total_active_fv", "total_fv_missed"],
    var_name="bucket", value_name="fv",
)
bar_long["bucket"] = bar_long["bucket"].map({
    "total_active_fv": "Captured (active)",
    "total_fv_missed": "Missed (on bench)",
})
fig_bar = px.bar(
    bar_long, x="player", y="fv", color="bucket",
    color_discrete_map={
        "Captured (active)": ACTIVE_COLOR,
        "Missed (on bench)": MISSED_COLOR,
    },
    category_orders={
        "player": team_ps.player.tolist(),
        "bucket": ["Captured (active)", "Missed (on bench)"],
    },
    custom_data=["player", "position", "apps_active", "apps_missed"],
)
fig_bar.update_traces(
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>Position: %{customdata[1]}<br>"
        "%{fullData.name}: %{y:.1f}<extra></extra>"
    ),
)
fig_bar.update_layout(
    barmode="stack", xaxis_tickangle=-45, yaxis_title="Fantavoto", xaxis_title="",
    legend_title_text="", legend=dict(orientation="h", yanchor="bottom",
                                       y=1.02, xanchor="right", x=1),
    height=520, margin=dict(l=10, r=10, t=30, b=10),
    clickmode="event+select",
)
event_bar = st.plotly_chart(
    fig_bar, width="stretch",
    on_select="rerun", selection_mode="points",
    key="td_squad_bar_select",
)
if event_bar.selection and event_bar.selection.points:
    p = event_bar.selection.points[0]
    cd = p.get("customdata") or []
    clicked_player = cd[0] if cd else p.get("x")
    if clicked_player:
        maybe_open_player_modal(league, comp, sel_team, clicked_player, key="td_squad_bar_select")

# ---- sunburst position -> player (clickable outer ring) ----
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
event_sun = st.plotly_chart(
    fig_sun, width="stretch",
    on_select="rerun", selection_mode="points",
    key="td_sunburst_select",
)
# Outer-ring sectors have a position as their parent (P/D/C/A); inner-ring
# sectors have parent="" (root). Only fire the player modal when an outer
# sector is clicked — let Plotly handle the inner-ring zoom-in itself.
if event_sun.selection and event_sun.selection.points:
    p = event_sun.selection.points[0]
    label = p.get("label")
    parent = p.get("parent")
    if label and parent in POSITION_ORDER:
        maybe_open_player_modal(league, comp, sel_team, label, key="td_sunburst_select")
st.caption(
    "Click a position slice to zoom in. Click a player slice (outer ring) "
    "to open that player's summary."
)

# ---- clickable player table ----
st.markdown("**Click a player row for a summary modal**")
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
    maybe_open_player_modal(league, comp, sel_team, selected.player, key="td_player_select")
