"""Player-season explorer with team/position/min-apps filters.

Clicking a player row opens Player Detail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

import i18n
from data import load_player_season, require_data
from i18n import t
from modals import maybe_open_player_modal
from theme import ACTIVE_COLOR, MISSED_COLOR, POSITION_COLOR, POSITION_ORDER


league, comp = require_data()
st.title(t("players.title"))
ps = load_player_season(league, comp)

# ---- filters ----
teams = sorted(ps.team.unique())
sel_teams = st.sidebar.multiselect(t("sidebar.team"), teams, default=teams)
sel_pos = st.sidebar.multiselect(t("sidebar.position"), POSITION_ORDER, default=POSITION_ORDER)

max_squad = int(ps.apps_in_squad.max())
min_apps = st.sidebar.slider(t("sidebar.min_apps"), 0, max_squad, 0)

sort_options = [
    "total_active_fv", "avg_active_fv", "pct_fv_captured", "pct_active_rate",
    "apps_active", "apps_missed", "total_fv_missed", "avg_fv_missed",
    "best_active_fv", "total_voto", "total_fv",
]
sort_col = st.sidebar.selectbox(
    t("sidebar.sort_by"), sort_options, index=0, format_func=i18n.col,
)

filtered = ps[
    ps.team.isin(sel_teams)
    & ps.position.isin(sel_pos)
    & (ps.apps_in_squad >= min_apps)
].sort_values(sort_col, ascending=False).reset_index(drop=True)

st.markdown(t("players.match_count", n=len(filtered)))

# ---- table (clickable) ----
event = st.dataframe(
    filtered,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="pl_select",
    column_config=i18n.columns_config(
        filtered,
        formats={"total_active_fv": "%.1f", "avg_active_fv": "%.2f",
                 "total_fv_missed": "%.1f", "avg_fv_missed": "%.2f",
                 "best_active_fv": "%.1f", "worst_active_fv": "%.1f",
                 "total_voto": "%.1f", "total_fv": "%.1f"},
        progress={"pct_fv_captured", "pct_active_rate"},
    ),
)
if event.selection.rows:
    row = filtered.iloc[event.selection.rows[0]]
    maybe_open_player_modal(league, comp, row.team, row.player, key="pl_select")

# ---- scatter: capture rate vs total active fv (positions in standard colour) ----
st.subheader(t("players.scatter_header"))
chart_df = filtered.dropna(subset=["pct_fv_captured", "total_active_fv"]).copy()
chart_df["capture_pct"] = (chart_df["pct_fv_captured"] * 100).round(1)
fig = px.scatter(
    chart_df,
    x="capture_pct", y="total_active_fv",
    color="position", size="apps_active",
    color_discrete_map=POSITION_COLOR,
    category_orders={"position": POSITION_ORDER},
    custom_data=["team", "player"],  # picked up by the click-selection event
    hover_data={"team": True, "player": True, "apps_active": True, "apps_missed": True},
    labels={"capture_pct": t("players.scatter_x"), "total_active_fv": t("players.scatter_y")},
)
fig.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=10))
event_pt = st.plotly_chart(
    fig,
    width="stretch",
    on_select="rerun",
    selection_mode="points",
    key="pl_scatter_select",
)
if event_pt.selection and event_pt.selection.points:
    p = event_pt.selection.points[0]
    cd = p.get("customdata") or []
    if len(cd) >= 2:
        maybe_open_player_modal(league, comp, cd[0], cd[1], key="pl_scatter_select")

st.caption(t("players.scatter_caption"))

# ---- player management quadrant: best- and worst-used players ----
# Uses the sidebar filters (sel_teams / sel_pos / min_apps) just like the
# table and the capture-rate scatter above.
st.subheader(t("players.quadrant_header"))

usage = filtered.dropna(subset=["avg_active_fv", "avg_fv_missed"]).copy()
usage["delta"] = usage["avg_active_fv"] - usage["avg_fv_missed"]

_cat_well = t("players.quadrant_well")
_cat_poor = t("players.quadrant_poor")
best = (usage[(usage.apps_active > 2) & (usage.delta > 0)]
            .sort_values("delta", ascending=False)
            .head(10)
            .assign(category=_cat_well))
worst = (usage[(usage.apps_missed > 2) & (usage.delta < 0)]
             .sort_values("delta", ascending=True)
             .head(10)
             .assign(category=_cat_poor))

if best.empty and worst.empty:
    st.info(t("players.quadrant_empty"))
else:
    quad = pd.concat([best, worst], ignore_index=True)

    fig_quad = px.scatter(
        quad,
        x="delta", y="apps_active", color="category",
        color_discrete_map={
            _cat_well: ACTIVE_COLOR,
            _cat_poor: MISSED_COLOR,
        },
        size="total_fv", size_max=32,
        text="player",
        custom_data=["team", "player", "position",
                     "avg_active_fv", "avg_fv_missed",
                     "apps_active", "apps_missed", "total_fv"],
        labels={
            "delta": t("players.quadrant_x"),
            "apps_active": t("players.quadrant_y"),
            "category": "",
        },
    )
    fig_quad.update_traces(
        textposition="top center",
        textfont=dict(size=10),
        hovertemplate=(
            "<b>%{customdata[1]}</b>  ·  %{customdata[2]}  ·  %{customdata[0]}<br>"
            + i18n.col("avg_active_fv") + ": %{customdata[3]:.2f}  ·  "
            + i18n.col("avg_fv_missed") + ": %{customdata[4]:.2f}<br>"
            "Δ: %{x:+.2f}<br>"
            + i18n.col("apps_active") + " / " + i18n.col("apps_missed")
            + ": %{customdata[5]} / %{customdata[6]}<br>"
            + i18n.col("total_fv") + ": %{customdata[7]:.1f}"
            "<extra></extra>"
        ),
    )
    fig_quad.add_vline(x=0, line_dash="dash", line_color="#888")
    if not quad.empty:
        median_apps = float(quad["apps_active"].median())
        fig_quad.add_hline(y=median_apps, line_dash="dot", line_color="#bbb")
    fig_quad.update_layout(
        height=540, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    event_quad = st.plotly_chart(
        fig_quad, width="stretch",
        on_select="rerun", selection_mode="points",
        key="pl_quad_select",
    )
    if event_quad.selection and event_quad.selection.points:
        p = event_quad.selection.points[0]
        cd = p.get("customdata") or []
        if len(cd) >= 2:
            maybe_open_player_modal(league, comp, cd[0], cd[1], key="pl_quad_select")

    st.markdown(t("players.quadrant_guide"))
