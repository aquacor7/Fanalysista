"""Single-player drill-in — appearance breakdown, voto details, distributions,
performance over time, and notable games."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import (
    load_appearances,
    load_matches,
    load_player_season,
    require_data,
)

# ---- constants ----
POSITION_LABEL = {"P": "Goalkeeper (P)", "D": "Defender (D)", "C": "Midfielder (C)", "A": "Attacker (A)"}
POSITION_COLOR = {"P": "#FFC107", "D": "#1E88E5", "C": "#43A047", "A": "#E53935"}
CATEGORY_COLOR = {
    "Starter":    "#2E7D32",   # dark green
    "Substitute": "#81C784",   # light green
    "Benched":    "#EF6C00",   # orange
    "No voto":    "#9E9E9E",   # grey
}
CATEGORY_ORDER = ["Starter", "Substitute", "Benched", "No voto"]


def _categorize(row: pd.Series) -> str:
    if pd.isna(row.voto):
        return "No voto"
    if not row.on_bench:
        return "Starter"   # in starting 11 with a real voto
    if row.active:
        return "Substitute"  # came on from the bench
    return "Benched"         # had voto but stayed on bench


# ---- page ----
st.set_page_config(page_title="Player Detail", layout="wide")
st.title("Player Detail")

league, comp = require_data()
ap = load_appearances(league, comp)
mt = load_matches(league, comp)
ps = load_player_season(league, comp)

# Sidebar: cascading team -> player
teams = sorted(ap.team.unique())
sel_team = st.sidebar.selectbox("Team", teams, key="pd_team")

team_players = (ps[ps.team == sel_team]
                .sort_values("total_fv", ascending=False)
                .player.tolist())
if not team_players:
    st.warning(f"No players found for {sel_team}.")
    st.stop()
sel_player = st.sidebar.selectbox("Player", team_players, key="pd_player")

# Filter to this player's appearances
me = ap[(ap.team == sel_team) & (ap.player == sel_player)].copy()
me = me.sort_values("giornata").reset_index(drop=True)
me["category"] = me.apply(_categorize, axis=1)

# Attach opponent per giornata
opps = mt[mt.team == sel_team][["giornata", "opponent", "result"]]
me = me.merge(opps, on="giornata", how="left")

# Convenience rows
season = ps[(ps.team == sel_team) & (ps.player == sel_player)].iloc[0]

# ---- header ----
position = me.position.iloc[0]
st.markdown(f"### {sel_player}  &nbsp;·&nbsp; {POSITION_LABEL[position]}  &nbsp;·&nbsp; {sel_team}")

# ---- KPI rows ----
n_starter = int((me.category == "Starter").sum())
n_sub = int((me.category == "Substitute").sum())
n_benched = int((me.category == "Benched").sum())
n_no_voto = int((me.category == "No voto").sum())
n_apps = n_starter + n_sub + n_benched
n_squad = len(me)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("In squad", n_squad)
c2.metric("Appearance (had voto)", n_apps)
c3.metric("Starter", n_starter)
c4.metric("Substitute", n_sub)
c5.metric("Benched / No voto", f"{n_benched} / {n_no_voto}")

st.divider()

# ---- appearance breakdown: pie + voto KPIs ----
col_pie, col_kpi = st.columns([1, 1])

with col_pie:
    st.subheader("Appearance breakdown")
    counts = (me.groupby("category").size()
                .reindex(CATEGORY_ORDER).fillna(0).astype(int))
    pie_df = pd.DataFrame({"category": counts.index, "count": counts.values})
    pie_df = pie_df[pie_df["count"] > 0]
    fig_pie = px.pie(
        pie_df, names="category", values="count",
        color="category", color_discrete_map=CATEGORY_COLOR, hole=0.4,
        category_orders={"category": CATEGORY_ORDER},
    )
    fig_pie.update_traces(
        textposition="inside", textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} giornate<extra></extra>",
    )
    fig_pie.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                          showlegend=False)
    st.plotly_chart(fig_pie, width="stretch")

with col_kpi:
    st.subheader("Voto details")
    a, b = st.columns(2)
    a.metric("Total voto", f"{season.total_voto:.1f}")
    b.metric("Total FV", f"{season.total_fv:.1f}")
    a.metric("Total active FV", f"{season.total_active_fv:.1f}")
    b.metric("Total FV missed", f"{season.total_fv_missed:.1f}")
    a.metric("Avg active FV", f"{season.avg_active_fv:.2f}"
                              if pd.notna(season.avg_active_fv) else "—")
    b.metric("Avg missed FV", f"{season.avg_fv_missed:.2f}"
                              if pd.notna(season.avg_fv_missed) else "—")

    # Manager-usage indicator
    if pd.notna(season.avg_active_fv) and pd.notna(season.avg_fv_missed):
        delta = season.avg_active_fv - season.avg_fv_missed
        if delta > 0.3:
            verdict = ("Well used", "green",
                       f"You played {sel_player} in his better games "
                       f"(active avg {delta:+.2f} vs missed avg).")
        elif delta < -0.3:
            sample_caveat = ("Note the small missed-game sample "
                             "— a single high score can skew this."
                             if n_benched <= 2 else "")
            verdict = ("Under used", "red",
                       f"You missed {sel_player}'s better games "
                       f"(active avg {delta:+.2f} vs missed avg). {sample_caveat}")
        else:
            verdict = ("Balanced", "grey",
                       f"Active and missed averages are close ({delta:+.2f}).")
        st.markdown(
            f"<div style='padding:10px;border-left:4px solid {verdict[1]};"
            f"background:#f7f7f7;'><b>{verdict[0]}.</b> {verdict[2]}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Not enough data on both sides (active and missed) for a usage verdict.")

st.divider()

# ---- performance over time ----
st.subheader("Performance over time")
plot_df = me[me.fantavoto.notna()].copy()
fig_bar = px.bar(
    plot_df, x="giornata", y="fantavoto", color="category",
    color_discrete_map=CATEGORY_COLOR,
    category_orders={"category": CATEGORY_ORDER},
    hover_data={"opponent": True, "result": True, "voto": True, "category": False},
)
fig_bar.update_layout(
    height=420, margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(dtick=1, title="Giornata"),
    yaxis_title="Fantavoto",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
# Add a horizontal line for the active average
if pd.notna(season.avg_active_fv):
    fig_bar.add_hline(y=season.avg_active_fv, line_dash="dash", line_color="#2E7D32",
                      annotation_text=f"avg active {season.avg_active_fv:.2f}",
                      annotation_position="top left")
st.plotly_chart(fig_bar, width="stretch")
st.caption("Bar colour: green = counted toward TOTALE, orange = had voto but didn't count.")

# ---- distribution: histogram + box plot ----
st.subheader("Distribution")
col_hist, col_box = st.columns(2)

with col_hist:
    fig_h = px.histogram(
        plot_df, x="fantavoto", color="category",
        color_discrete_map=CATEGORY_COLOR,
        category_orders={"category": CATEGORY_ORDER},
        nbins=20, opacity=0.85,
    )
    fig_h.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title="Fantavoto", yaxis_title="Count",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                    xanchor="right", x=1))
    st.plotly_chart(fig_h, width="stretch")
    st.caption("Right-skewed = boom games are rare; tightly-clustered = steady.")

with col_box:
    box_df = plot_df.copy()
    # group active vs missed for the box plot
    box_df["bucket"] = np.where(box_df.active, "Active", "Missed")
    fig_box = px.box(
        box_df, x="bucket", y="fantavoto", color="bucket", points="all",
        color_discrete_map={"Active": "#2E7D32", "Missed": "#EF6C00"},
    )
    fig_box.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                          showlegend=False, xaxis_title="", yaxis_title="Fantavoto")
    st.plotly_chart(fig_box, width="stretch")
    st.caption(
        f"Active median {plot_df[plot_df.active].fantavoto.median() if plot_df.active.any() else 0:.1f} "
        f"vs missed median {plot_df[~plot_df.active].fantavoto.median() if (~plot_df.active).any() else 0:.1f}. "
        "A wider box = more boom-or-bust."
    )

st.divider()

# ---- notable games + comparisons ----
left, right = st.columns(2)

with left:
    st.subheader("Notable games")
    notable_rows = []
    active_pl = plot_df[plot_df.active]
    missed_pl = plot_df[~plot_df.active & plot_df.fantavoto.notna()]
    if not active_pl.empty:
        best = active_pl.loc[active_pl.fantavoto.idxmax()]
        notable_rows.append(("Best active game",
                             f"g{int(best.giornata)} vs {best.opponent}",
                             f"{best.fantavoto:.1f} fv"))
        worst = active_pl.loc[active_pl.fantavoto.idxmin()]
        notable_rows.append(("Worst active game",
                             f"g{int(worst.giornata)} vs {worst.opponent}",
                             f"{worst.fantavoto:.1f} fv"))
    if not missed_pl.empty:
        biggest_miss = missed_pl.loc[missed_pl.fantavoto.idxmax()]
        notable_rows.append(("Biggest missed game",
                             f"g{int(biggest_miss.giornata)} vs {biggest_miss.opponent}",
                             f"{biggest_miss.fantavoto:.1f} fv"))
    # longest active streak
    if not me.empty:
        streak = max_streak = cur = 0
        for is_active in me.active.tolist():
            cur = cur + 1 if is_active else 0
            max_streak = max(max_streak, cur)
        notable_rows.append(("Longest active streak", f"{max_streak} giornate", ""))

    nf = pd.DataFrame(notable_rows, columns=["What", "When", "Value"])
    st.dataframe(nf, width="stretch", hide_index=True)

with right:
    st.subheader("Vs peers at same position")
    # Team peers
    team_peers = ps[(ps.team == sel_team) & (ps.position == position)]
    team_peer_avg = team_peers.avg_active_fv.dropna().mean()
    team_rank = (team_peers.sort_values("total_active_fv", ascending=False)
                          .reset_index(drop=True))
    my_rank_in_team = team_rank[team_rank.player == sel_player].index[0] + 1

    # League peers
    league_peers = ps[ps.position == position]
    league_peer_avg = league_peers.avg_active_fv.dropna().mean()
    league_rank_df = (league_peers.sort_values("total_active_fv", ascending=False)
                                 .reset_index(drop=True))
    my_row = league_rank_df[
        (league_rank_df.team == sel_team) & (league_rank_df.player == sel_player)
    ]
    my_rank_in_league = int(my_row.index[0]) + 1 if not my_row.empty else None

    rows = [
        ("Your avg active FV", f"{season.avg_active_fv:.2f}"
                                if pd.notna(season.avg_active_fv) else "—",
         ""),
        ("Team avg (same position)", f"{team_peer_avg:.2f}"
                                      if pd.notna(team_peer_avg) else "—",
         f"{(season.avg_active_fv - team_peer_avg):+.2f}"
         if pd.notna(season.avg_active_fv) and pd.notna(team_peer_avg) else ""),
        ("League avg (same position)", f"{league_peer_avg:.2f}"
                                        if pd.notna(league_peer_avg) else "—",
         f"{(season.avg_active_fv - league_peer_avg):+.2f}"
         if pd.notna(season.avg_active_fv) and pd.notna(league_peer_avg) else ""),
        ("Rank in team (by total active FV)",
         f"#{my_rank_in_team} of {len(team_rank)}", ""),
        ("Rank in league at this position",
         f"#{my_rank_in_league} of {len(league_rank_df)}" if my_rank_in_league else "—",
         ""),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Metric", "Value", "Δ"]),
                 width="stretch", hide_index=True)

# ---- raw table ----
with st.expander("Raw per-giornata appearances"):
    show = me[["giornata", "opponent", "result", "category",
               "position", "voto", "fantavoto", "active", "on_bench"]]
    st.dataframe(show, width="stretch", hide_index=True,
                 column_config={
                     "voto": st.column_config.NumberColumn(format="%.1f"),
                     "fantavoto": st.column_config.NumberColumn(format="%.1f"),
                 })
