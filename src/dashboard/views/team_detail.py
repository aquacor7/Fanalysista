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

import i18n
from data import (
    load_matches,
    load_player_season,
    load_team_season,
    persist_sidebar_selectbox,
    require_data,
)
from i18n import t
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


league, comp = require_data()
mt = load_matches(league, comp)
ps = load_player_season(league, comp)
ts = load_team_season(league, comp)

# ---- sidebar team picker (persists across nav via canonical key) ----
teams = sorted(mt.team.unique())
sel_team = persist_sidebar_selectbox(
    t("sidebar.team"), teams, widget_key="selected_team", canon_key="_canon_team",
)

breadcrumbs(
    (t("nav.league_table"), "views/league_table.py"),
    (sel_team, None),
)
st.title(sel_team)

# ---- season KPI row ----
team_row = ts[ts.team == sel_team].iloc[0]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(t("common.wdl"), f"{int(team_row.wins)} / {int(team_row.draws)} / {int(team_row.losses)}")
c2.metric(t("common.points"), int(team_row.points))
c3.metric(t("common.avg_totale"), f"{team_row.totale_avg:.2f}")
c4.metric(t("common.goal_diff"), f"{int(team_row.goal_diff):+d}")
if "regret_total" in ts.columns and pd.notna(team_row.get("regret_total")):
    c5.metric(
        t("team_detail.regret_total"),
        f"{team_row.regret_total:.1f}",
        delta=t("team_detail.perfect_g_delta", n=int(team_row.get('perfect_giornate', 0))),
        delta_color="off",
    )

st.divider()

# ============================================================
# 1. Schedule
# ============================================================
st.subheader(t("team_detail.schedule_header"))

opp = mt[["giornata", "team", "totale"]].rename(
    columns={"team": "opponent", "totale": "opp_totale"})
schedule = (mt[mt.team == sel_team]
              .merge(opp, on=["giornata", "opponent"], how="left")
              .sort_values("giornata"))
view = schedule[[
    "giornata", "opponent", "side", "result",
    "score_for", "score_against", "totale", "opp_totale", "module",
]].copy()
# Localise the home/away side values (they're derived labels, not raw data).
view["side"] = view["side"].map({"home": t("side.home"), "away": t("side.away")}).fillna(view["side"])
st.dataframe(
    view,
    width="stretch",
    hide_index=True,
    column_config=i18n.columns_config(
        view,
        formats={"totale": "%.1f", "opp_totale": "%.1f",
                 "score_for": "%d", "score_against": "%d"},
    ),
)

st.markdown(t("team_detail.trend_header"))
trend_df = (
    schedule[["giornata", "totale", "opp_totale"]]
      .melt(id_vars="giornata", var_name="who", value_name="value")
)
opponent_label = t("team_detail.opponent")
trend_df["who"] = trend_df["who"].map({"totale": sel_team, "opp_totale": opponent_label})

fig_trend = px.line(
    trend_df, x="giornata", y="value", color="who", markers=True,
    color_discrete_map={sel_team: SUBJECT_COLOR, opponent_label: OPPONENT_COLOR},
    labels={"value": i18n.col("totale"), "giornata": i18n.col("giornata"), "who": ""},
)
fig_trend.update_layout(
    height=380, hovermode="x unified",
    margin=dict(l=10, r=10, t=10, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig_trend, width="stretch")
st.caption(t("team_detail.trend_caption", team=sel_team))

st.divider()

# ============================================================
# 2. Squad composition
# ============================================================
st.subheader(t("team_detail.squad_header"))

team_ps = ps[ps.team == sel_team].copy()

_sort_opts = ["total_fv", "active_fv", "missed_fv", "pos_name"]
sort_mode = st.radio(
    t("team_detail.sort_prompt"),
    _sort_opts,
    format_func=lambda o: t(f"team_detail.sort_{o}"),
    horizontal=True, index=0,
)
if sort_mode == "active_fv":
    team_ps = team_ps.sort_values("total_active_fv", ascending=False)
elif sort_mode == "missed_fv":
    team_ps = team_ps.sort_values("total_fv_missed", ascending=False)
elif sort_mode == "pos_name":
    team_ps["_o"] = team_ps.position.map({p: i for i, p in enumerate(POSITION_ORDER)})
    team_ps = team_ps.sort_values(["_o", "player"]).drop(columns="_o")
else:
    team_ps = team_ps.sort_values("total_fv", ascending=False)

# ---- stacked bar: per-player active + missed (clickable) ----
st.markdown(t("team_detail.bar_prompt"))
# Long-format dataframe so px.bar attaches per-row customdata identically across
# both stacked traces — makes click→player extraction robust regardless of which
# segment the user clicked.
bar_long = team_ps.melt(
    id_vars=["player", "position", "apps_active", "apps_missed"],
    value_vars=["total_active_fv", "total_fv_missed"],
    var_name="bucket", value_name="fv",
)
_bar_captured = t("team_detail.bar_captured")
_bar_missed = t("team_detail.bar_missed")
bar_long["bucket"] = bar_long["bucket"].map({
    "total_active_fv": _bar_captured,
    "total_fv_missed": _bar_missed,
})
fig_bar = px.bar(
    bar_long, x="player", y="fv", color="bucket",
    color_discrete_map={
        _bar_captured: ACTIVE_COLOR,
        _bar_missed: MISSED_COLOR,
    },
    category_orders={
        "player": team_ps.player.tolist(),
        "bucket": [_bar_captured, _bar_missed],
    },
    custom_data=["player", "position", "apps_active", "apps_missed"],
)
fig_bar.update_traces(
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>" + i18n.col("position") + ": %{customdata[1]}<br>"
        "%{fullData.name}: %{y:.1f}<extra></extra>"
    ),
)
fig_bar.update_layout(
    barmode="stack", xaxis_tickangle=-45, yaxis_title=t("team_detail.bar_axis"), xaxis_title="",
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
st.markdown(t("team_detail.sunburst_prompt"))
sun_df = team_ps[team_ps.total_active_fv > 0]
fig_sun = px.sunburst(
    sun_df, path=["position", "player"], values="total_active_fv",
    color="position", color_discrete_map=POSITION_COLOR, branchvalues="total",
)
fig_sun.update_traces(
    textinfo="label+percent parent",
    hovertemplate="<b>%{label}</b><br>" + i18n.col("total_active_fv") + ": %{value:.1f}<br>"
                  "%{percentParent:.1%}<extra></extra>",
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
st.caption(t("team_detail.sunburst_caption"))

# ---- clickable player table ----
st.markdown(t("team_detail.player_table_prompt"))
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
    column_config=i18n.columns_config(
        player_table,
        formats={"total_active_fv": "%.1f", "total_fv_missed": "%.1f",
                 "total_fv": "%.1f", "avg_active_fv": "%.2f"},
        progress={"pct_fv_captured"},
    ),
)
if event.selection.rows:
    selected = player_table.iloc[event.selection.rows[0]]
    maybe_open_player_modal(league, comp, sel_team, selected.player, key="td_player_select")
