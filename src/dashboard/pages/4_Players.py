"""Player-season explorer with team/position/min-apps filters.

Clicking a player row opens Player Detail.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from data import load_player_season, require_data
from modals import maybe_open_player_modal
from theme import ACTIVE_COLOR, MISSED_COLOR, POSITION_COLOR, POSITION_ORDER

st.set_page_config(page_title="Players", layout="wide")
st.title("Players")

league, comp = require_data()
ps = load_player_season(league, comp)

# ---- filters ----
teams = sorted(ps.team.unique())
sel_teams = st.sidebar.multiselect("Team", teams, default=teams)
sel_pos = st.sidebar.multiselect("Position", POSITION_ORDER, default=POSITION_ORDER)

max_squad = int(ps.apps_in_squad.max())
min_apps = st.sidebar.slider("Min apps in squad", 0, max_squad, 0)

sort_options = [
    "total_active_fv", "avg_active_fv", "pct_fv_captured", "pct_active_rate",
    "apps_active", "apps_missed", "total_fv_missed", "avg_fv_missed",
    "best_active_fv", "total_voto", "total_fv",
]
sort_col = st.sidebar.selectbox("Sort by", sort_options, index=0)

filtered = ps[
    ps.team.isin(sel_teams)
    & ps.position.isin(sel_pos)
    & (ps.apps_in_squad >= min_apps)
].sort_values(sort_col, ascending=False).reset_index(drop=True)

st.markdown(f"**{len(filtered)} players** match filters — click a row (or a dot in the chart below) for a summary modal")

# ---- table (clickable) ----
event = st.dataframe(
    filtered,
    width="stretch",
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="pl_select",
    column_config={
        "pct_fv_captured": st.column_config.ProgressColumn(
            "% FV captured", min_value=0.0, max_value=1.0, format="percent",
        ),
        "pct_active_rate": st.column_config.ProgressColumn(
            "% Active rate", min_value=0.0, max_value=1.0, format="percent",
        ),
        "total_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "avg_active_fv": st.column_config.NumberColumn(format="%.2f"),
        "total_fv_missed": st.column_config.NumberColumn(format="%.1f"),
        "avg_fv_missed": st.column_config.NumberColumn(format="%.2f"),
        "best_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "worst_active_fv": st.column_config.NumberColumn(format="%.1f"),
        "total_voto": st.column_config.NumberColumn(format="%.1f"),
        "total_fv": st.column_config.NumberColumn(format="%.1f"),
    },
)
if event.selection.rows:
    row = filtered.iloc[event.selection.rows[0]]
    maybe_open_player_modal(league, comp, row.team, row.player, key="pl_select")

# ---- scatter: capture rate vs total active fv (positions in standard colour) ----
st.subheader("Capture rate vs total active FV")
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
    labels={"capture_pct": "% FV captured", "total_active_fv": "Total active FV"},
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

st.caption(
    "Top-right = high contribution AND high efficiency. "
    "Top-left = scored a lot but you missed a lot too (high-regret player). "
    "Click any dot to open that player's summary."
)

# ---- player management quadrant: best- and worst-used players ----
# Uses the sidebar filters (sel_teams / sel_pos / min_apps) just like the
# table and the capture-rate scatter above.
st.subheader("Player management — best & worst used")

usage = filtered.dropna(subset=["avg_active_fv", "avg_fv_missed"]).copy()
usage["delta"] = usage["avg_active_fv"] - usage["avg_fv_missed"]

best = (usage[(usage.apps_active > 2) & (usage.delta > 0)]
            .sort_values("delta", ascending=False)
            .head(10)
            .assign(category="Well used (top 10)"))
worst = (usage[(usage.apps_missed > 2) & (usage.delta < 0)]
             .sort_values("delta", ascending=True)
             .head(10)
             .assign(category="Poorly used (top 10)"))

if best.empty and worst.empty:
    st.info(
        "No players match the current filters with enough active/missed apps "
        "to rank usage extremes. Try loosening the Team / Position / Min apps "
        "filters in the sidebar."
    )
else:
    quad = pd.concat([best, worst], ignore_index=True)

    fig_quad = px.scatter(
        quad,
        x="delta", y="apps_active", color="category",
        color_discrete_map={
            "Well used (top 10)": ACTIVE_COLOR,
            "Poorly used (top 10)": MISSED_COLOR,
        },
        size="total_fv", size_max=32,
        text="player",
        custom_data=["team", "player", "position",
                     "avg_active_fv", "avg_fv_missed",
                     "apps_active", "apps_missed", "total_fv"],
        labels={
            "delta": "Avg active FV − Avg missed FV",
            "apps_active": "Active appearances",
            "category": "",
        },
    )
    fig_quad.update_traces(
        textposition="top center",
        textfont=dict(size=10),
        hovertemplate=(
            "<b>%{customdata[1]}</b>  ·  %{customdata[2]}  ·  %{customdata[0]}<br>"
            "Avg active FV: %{customdata[3]:.2f}  ·  "
            "Avg missed FV: %{customdata[4]:.2f}<br>"
            "Δ (active − missed): %{x:+.2f}<br>"
            "Apps active / missed: %{customdata[5]} / %{customdata[6]}<br>"
            "Total FV (bubble size): %{customdata[7]:.1f}"
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

    st.markdown(
        "**How to read this chart**\n\n"
        "- **X-axis** — Avg active FV minus Avg missed FV. Right of the dashed "
        "line = you used the player in his better games; left = you missed his "
        "better games.\n"
        "- **Y-axis** — active appearances. Top half = key fixture in the lineup; "
        "bottom half = bench/sub.\n"
        "- **Bubble size** — Total FV across all appearances (active + missed). "
        "Bigger bubble = bigger management impact on the season.\n"
        "- **Filters** — well-used requires `apps_active > 2`; poorly-used "
        "requires `apps_missed > 2`. The sidebar Team / Position / Min apps "
        "filters apply too.\n\n"
        "**Quadrant guide**\n\n"
        "- **Top-right** — key well-used player.\n"
        "- **Top-left** — poorly-used starter (would have scored more from the bench).\n"
        "- **Bottom-right** — effective substitute (used sparingly, but well).\n"
        "- **Bottom-left** — missed bench (rarely fielded; did better off the field).\n\n"
        "_Click any point to open that player's summary._"
    )
