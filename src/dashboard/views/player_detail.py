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

import i18n
from data import (
    load_appearances,
    load_matches,
    load_player_season,
    persist_sidebar_selectbox,
    require_data,
)
from i18n import t
from theme import CATEGORY_COLOR, CATEGORY_ORDER
from ui import breadcrumbs


def _categorize(row: pd.Series) -> str:
    if pd.isna(row.voto):
        return "No voto"
    if not row.on_bench:
        return "Starter"   # in starting 11 with a real voto
    if row.active:
        return "Substitute"  # came on from the bench
    return "Benched"         # had voto but stayed on bench


# ---- page ----

league, comp = require_data()
ap = load_appearances(league, comp)
mt = load_matches(league, comp)
ps = load_player_season(league, comp)

# Sidebar: cascading team -> player. Both are backed by canonical keys
# (_canon_team, _canon_player) so the selection survives modal AND sidebar
# navigation.
teams = sorted(ap.team.unique())
sel_team = persist_sidebar_selectbox(
    t("sidebar.team"), teams, widget_key="selected_team", canon_key="_canon_team",
)

team_players = (ps[ps.team == sel_team]
                .sort_values("total_fv", ascending=False)
                .player.tolist())
if not team_players:
    st.warning(t("player_detail.no_players", team=sel_team))
    st.stop()

sel_player = persist_sidebar_selectbox(
    t("sidebar.player"), team_players,
    widget_key="selected_player", canon_key="_canon_player",
)

# Filter to this player's appearances
me = ap[(ap.team == sel_team) & (ap.player == sel_player)].copy()
me = me.sort_values("giornata").reset_index(drop=True)
me["category"] = me.apply(_categorize, axis=1)

# Attach opponent per giornata
opps = mt[mt.team == sel_team][["giornata", "opponent", "result"]]
me = me.merge(opps, on="giornata", how="left")

# Convenience rows
season = ps[(ps.team == sel_team) & (ps.player == sel_player)].iloc[0]

# ---- breadcrumbs + header ----
breadcrumbs(
    (t("nav.league_table"), "views/league_table.py"),
    (sel_team, "views/team_detail.py"),
    (sel_player, None),
)
position = me.position.iloc[0]
st.markdown(f"### {sel_player}  &nbsp;·&nbsp; {t(f'pos.{position}')}  &nbsp;·&nbsp; {sel_team}")

# Translated appearance-category maps (categories stay English in the data for
# grouping/counting; we only translate at display points).
CAT_ORDER_T = [i18n.cat(c) for c in CATEGORY_ORDER]
CAT_COLOR_T = {i18n.cat(k): v for k, v in CATEGORY_COLOR.items()}

# ---- KPI rows ----
n_starter = int((me.category == "Starter").sum())
n_sub = int((me.category == "Substitute").sum())
n_benched = int((me.category == "Benched").sum())
n_no_voto = int((me.category == "No voto").sum())
n_apps = n_starter + n_sub + n_benched
n_squad = len(me)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(t("player_detail.in_squad"), n_squad)
c2.metric(t("player_detail.appearance_voto"), n_apps)
c3.metric(t("player_detail.starter"), n_starter)
c4.metric(t("player_detail.substitute"), n_sub)
c5.metric(t("player_detail.benched_no_voto"), f"{n_benched} / {n_no_voto}")

st.divider()

# ---- appearance breakdown: pie + voto KPIs ----
col_pie, col_kpi = st.columns([1, 1])

with col_pie:
    st.subheader(t("player_detail.appearance_header"))
    counts = (me.groupby("category").size()
                .reindex(CATEGORY_ORDER).fillna(0).astype(int))
    pie_df = pd.DataFrame({"category": [i18n.cat(c) for c in counts.index],
                           "count": counts.values})
    pie_df = pie_df[pie_df["count"] > 0]
    fig_pie = px.pie(
        pie_df, names="category", values="count",
        color="category", color_discrete_map=CAT_COLOR_T, hole=0.4,
        category_orders={"category": CAT_ORDER_T},
    )
    fig_pie.update_traces(
        textposition="inside", textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} " + i18n.col("giornata") + "<extra></extra>",
    )
    fig_pie.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                          showlegend=False)
    st.plotly_chart(fig_pie, width="stretch")

with col_kpi:
    st.subheader(t("player_detail.voto_header"))
    a, b = st.columns(2)
    a.metric(t("player_detail.total_voto"), f"{season.total_voto:.1f}")
    b.metric(t("player_detail.total_fv"), f"{season.total_fv:.1f}")
    a.metric(t("player_detail.total_active_fv"), f"{season.total_active_fv:.1f}")
    b.metric(t("player_detail.total_fv_missed"), f"{season.total_fv_missed:.1f}")
    a.metric(t("player_detail.avg_active_fv"), f"{season.avg_active_fv:.2f}"
                              if pd.notna(season.avg_active_fv) else "—")
    b.metric(t("player_detail.avg_missed_fv"), f"{season.avg_fv_missed:.2f}"
                              if pd.notna(season.avg_fv_missed) else "—")

    # Manager-usage indicator
    if pd.notna(season.avg_active_fv) and pd.notna(season.avg_fv_missed):
        delta = season.avg_active_fv - season.avg_fv_missed
        if delta > 0.3:
            verdict = (t("player_detail.verdict_well_title"), "green",
                       t("player_detail.verdict_well_text",
                         player=sel_player, delta=f"{delta:+.2f}"))
        elif delta < -0.3:
            caveat = (t("player_detail.verdict_under_caveat")
                      if n_benched <= 2 else "")
            verdict = (t("player_detail.verdict_under_title"), "red",
                       t("player_detail.verdict_under_text",
                         player=sel_player, delta=f"{delta:+.2f}", caveat=caveat))
        else:
            verdict = (t("player_detail.verdict_balanced_title"), "grey",
                       t("player_detail.verdict_balanced_text", delta=f"{delta:+.2f}"))
        st.markdown(
            f"<div style='padding:10px;border-left:4px solid {verdict[1]};"
            f"background:#f7f7f7;'><b>{verdict[0]}.</b> {verdict[2]}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info(t("player_detail.verdict_insufficient"))

st.divider()

# ---- performance over time ----
st.subheader(t("player_detail.performance_header"))
plot_df = me[me.fantavoto.notna()].copy()
plot_df["category_disp"] = plot_df["category"].map(i18n.cat)
fig_bar = px.bar(
    plot_df, x="giornata", y="fantavoto", color="category_disp",
    color_discrete_map=CAT_COLOR_T,
    category_orders={"category_disp": CAT_ORDER_T},
    hover_data={"opponent": True, "result": True, "voto": True, "category_disp": False},
)
fig_bar.update_layout(
    height=420, margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(dtick=1, title=i18n.col("giornata")),
    yaxis_title=i18n.col("fantavoto"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
# Add a horizontal line for the active average
if pd.notna(season.avg_active_fv):
    fig_bar.add_hline(y=season.avg_active_fv, line_dash="dash", line_color="#2E7D32",
                      annotation_text=t("player_detail.avg_active_annotation",
                                        value=f"{season.avg_active_fv:.2f}"),
                      annotation_position="top left")
st.plotly_chart(fig_bar, width="stretch")
st.caption(t("player_detail.performance_caption"))

# ---- distribution: histogram + box plot ----
st.subheader(t("player_detail.dist_header"))
col_hist, col_box = st.columns(2)

with col_hist:
    fig_h = px.histogram(
        plot_df, x="fantavoto", color="category_disp",
        color_discrete_map=CAT_COLOR_T,
        category_orders={"category_disp": CAT_ORDER_T},
        nbins=20, opacity=0.85,
    )
    fig_h.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title=i18n.col("fantavoto"), yaxis_title=t("player_detail.count_axis"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                    xanchor="right", x=1))
    st.plotly_chart(fig_h, width="stretch")
    st.caption(t("player_detail.hist_caption"))

with col_box:
    box_df = plot_df.copy()
    # group active vs missed for the box plot
    box_df["bucket"] = np.where(box_df.active, t("player_detail.box_active"),
                                t("player_detail.box_missed"))
    fig_box = px.box(
        box_df, x="bucket", y="fantavoto", color="bucket", points="all",
        color_discrete_map={t("player_detail.box_active"): "#2E7D32",
                            t("player_detail.box_missed"): "#EF6C00"},
    )
    fig_box.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                          showlegend=False, xaxis_title="", yaxis_title=i18n.col("fantavoto"))
    st.plotly_chart(fig_box, width="stretch")
    st.caption(t(
        "player_detail.box_caption",
        active=f"{plot_df[plot_df.active].fantavoto.median() if plot_df.active.any() else 0:.1f}",
        missed=f"{plot_df[~plot_df.active].fantavoto.median() if (~plot_df.active).any() else 0:.1f}",
    ))

st.divider()

# ---- notable games + comparisons ----
left, right = st.columns(2)

with left:
    st.subheader(t("player_detail.notable_header"))
    notable_rows = []
    active_pl = plot_df[plot_df.active]
    missed_pl = plot_df[~plot_df.active & plot_df.fantavoto.notna()]
    if not active_pl.empty:
        best = active_pl.loc[active_pl.fantavoto.idxmax()]
        notable_rows.append((t("player_detail.notable_best"),
                             t("player_detail.notable_vs", g=int(best.giornata), opp=best.opponent),
                             t("player_detail.notable_fv", fv=f"{best.fantavoto:.1f}")))
        worst = active_pl.loc[active_pl.fantavoto.idxmin()]
        notable_rows.append((t("player_detail.notable_worst"),
                             t("player_detail.notable_vs", g=int(worst.giornata), opp=worst.opponent),
                             t("player_detail.notable_fv", fv=f"{worst.fantavoto:.1f}")))
    if not missed_pl.empty:
        biggest_miss = missed_pl.loc[missed_pl.fantavoto.idxmax()]
        notable_rows.append((t("player_detail.notable_biggest_miss"),
                             t("player_detail.notable_vs", g=int(biggest_miss.giornata), opp=biggest_miss.opponent),
                             t("player_detail.notable_fv", fv=f"{biggest_miss.fantavoto:.1f}")))
    # longest active streak
    if not me.empty:
        streak = max_streak = cur = 0
        for is_active in me.active.tolist():
            cur = cur + 1 if is_active else 0
            max_streak = max(max_streak, cur)
        notable_rows.append((t("player_detail.notable_streak"),
                             t("player_detail.notable_streak_value", n=max_streak), ""))

    nf = pd.DataFrame(notable_rows, columns=[
        t("player_detail.notable_col_what"),
        t("player_detail.notable_col_when"),
        t("player_detail.notable_col_value")])
    st.dataframe(nf, width="stretch", hide_index=True)

with right:
    st.subheader(t("player_detail.peers_header"))
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
        (t("player_detail.peers_your_avg"), f"{season.avg_active_fv:.2f}"
                                if pd.notna(season.avg_active_fv) else "—",
         ""),
        (t("player_detail.peers_team_avg"), f"{team_peer_avg:.2f}"
                                      if pd.notna(team_peer_avg) else "—",
         f"{(season.avg_active_fv - team_peer_avg):+.2f}"
         if pd.notna(season.avg_active_fv) and pd.notna(team_peer_avg) else ""),
        (t("player_detail.peers_league_avg"), f"{league_peer_avg:.2f}"
                                        if pd.notna(league_peer_avg) else "—",
         f"{(season.avg_active_fv - league_peer_avg):+.2f}"
         if pd.notna(season.avg_active_fv) and pd.notna(league_peer_avg) else ""),
        (t("player_detail.peers_rank_team"),
         t("player_detail.peers_rank_value", rank=my_rank_in_team, total=len(team_rank)), ""),
        (t("player_detail.peers_rank_league"),
         t("player_detail.peers_rank_value", rank=my_rank_in_league, total=len(league_rank_df))
         if my_rank_in_league else "—", ""),
    ]
    st.dataframe(pd.DataFrame(rows, columns=[
        t("player_detail.peers_col_metric"), t("player_detail.peers_col_value"), "Δ"]),
                 width="stretch", hide_index=True)

# ---- raw table ----
with st.expander(t("player_detail.raw_expander")):
    show = me[["giornata", "opponent", "result", "category",
               "position", "voto", "fantavoto", "active", "on_bench"]].copy()
    show["category"] = show["category"].map(i18n.cat)
    st.dataframe(show, width="stretch", hide_index=True,
                 column_config=i18n.columns_config(
                     show, formats={"voto": "%.1f", "fantavoto": "%.1f"}))
