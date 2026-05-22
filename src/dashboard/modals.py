"""Reusable @st.dialog modals for clicking-to-peek at teams and players.

Two design points:
    - The modal is a *digest*, not the full page. It shows the headline numbers
      and one small chart. A primary button at the bottom escalates to the
      corresponding full Detail page if the user wants to dig deeper.
    - Each click handler in a page calls `maybe_open_team_modal()` /
      `maybe_open_player_modal()`. Those helpers compare the new selection
      against `st.session_state` so the modal only opens on a transition,
      preventing the dialog from re-opening on every rerun while a row stays
      selected.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data import (
    load_appearances,
    load_matches,
    load_player_season,
    load_team_season,
)
from theme import (
    ACTIVE_COLOR,
    MISSED_COLOR,
    OPPONENT_COLOR,
    SUBJECT_COLOR,
)


# --------------- internal: transition guards ---------------
#
# We use TWO levels of guard to prevent modal-open misfires:
#
# 1. Per-widget "last selection" guard (keyed by caller's `key`). This
#    stops the modal from re-opening on every rerun while a chart/table row
#    stays selected, AND lets the SAME team/player be opened from DIFFERENT
#    widgets (the previous global guards blocked this — see issue 1).
#
# 2. Per-run "already opened a dialog" flag. Streamlit forbids two
#    `@st.dialog` calls in the same script run (duplicate element ID). When
#    multiple widgets on the page each have a persisted selection, both
#    handlers fire on a rerun — we let only the first one through (see
#    issue 2). The flag is reset at the top of each script run by
#    `require_data()` in `data.py`.

_DIALOG_OPENED_THIS_RUN = "_modal_opened_this_run"


def _last_sel_key(prefix: str, key: str) -> str:
    return f"_last_{prefix}_modal_sel_{key}"


def reset_per_run_modal_state() -> None:
    """Called by require_data() at the start of every page render."""
    st.session_state[_DIALOG_OPENED_THIS_RUN] = False


def maybe_open_team_modal(league: str, comp: str, team: str, *, key: str) -> None:
    """Open the team modal if `team` is a fresh selection from this widget.

    `key` must be the caller widget's unique identifier (the same string
    passed to ``st.dataframe(..., key=...)`` or ``st.plotly_chart(..., key=...)``).
    """
    if not team:
        return
    if st.session_state.get(_DIALOG_OPENED_THIS_RUN):
        return
    sel_key = _last_sel_key("team", key)
    if st.session_state.get(sel_key) == team:
        return
    st.session_state[sel_key] = team
    st.session_state[_DIALOG_OPENED_THIS_RUN] = True
    _team_modal(league, comp, team)


def maybe_open_player_modal(
    league: str, comp: str, team: str, player: str, *, key: str,
) -> None:
    if not team or not player:
        return
    if st.session_state.get(_DIALOG_OPENED_THIS_RUN):
        return
    sel_key = _last_sel_key("player", key)
    selection = (team, player)
    if st.session_state.get(sel_key) == selection:
        return
    st.session_state[sel_key] = selection
    st.session_state[_DIALOG_OPENED_THIS_RUN] = True
    _player_modal(league, comp, team, player)


# --------------- the modals ---------------

@st.dialog("Team summary", width="large")
def _team_modal(league: str, comp: str, team: str) -> None:
    ts = load_team_season(league, comp)
    mt = load_matches(league, comp)
    ps = load_player_season(league, comp)

    row = ts[ts.team == team].iloc[0]
    st.markdown(f"### {team}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("W / D / L", f"{int(row.wins)} / {int(row.draws)} / {int(row.losses)}")
    c2.metric("Points", int(row.points))
    c3.metric("Avg TOTALE", f"{row.totale_avg:.2f}")
    c4.metric("Goal diff", f"{int(row.goal_diff):+d}")

    if "regret_total" in ts.columns and pd.notna(row.get("regret_total")):
        st.caption(
            f"Season regret: **{row.regret_total:.1f}**  ·  "
            f"perfect giornate: **{int(row.get('perfect_giornate', 0))}**"
        )

    # Mini TOTALE-vs-opp trend
    opp = mt[["giornata", "team", "totale"]].rename(
        columns={"team": "opponent", "totale": "opp_totale"})
    s = mt[mt.team == team].merge(opp, on=["giornata", "opponent"], how="left").sort_values("giornata")
    trend = s[["giornata", "totale", "opp_totale"]].melt(
        id_vars="giornata", var_name="who", value_name="value")
    trend["who"] = trend["who"].map({"totale": team, "opp_totale": "Opponent"})
    fig = px.line(
        trend, x="giornata", y="value", color="who", markers=False,
        color_discrete_map={team: SUBJECT_COLOR, "Opponent": OPPONENT_COLOR},
        labels={"value": "TOTALE", "giornata": "Giornata", "who": ""},
    )
    fig.update_layout(
        height=220, hovermode="x unified",
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch", key=f"team_modal_trend_{team}")

    # Top contributors
    st.markdown("**Top 5 contributors**")
    top = (ps[ps.team == team]
              .sort_values("total_active_fv", ascending=False)
              .head(5))
    st.dataframe(
        top[["position", "player", "apps_active", "total_active_fv",
             "avg_active_fv", "pct_fv_captured"]],
        width="stretch", hide_index=True,
        column_config={
            "pct_fv_captured": st.column_config.ProgressColumn(
                "% captured", min_value=0.0, max_value=1.0, format="percent"),
            "total_active_fv": st.column_config.NumberColumn(format="%.1f"),
            "avg_active_fv": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    if st.button(f"Open full Team Detail for {team} →",
                 width="stretch", type="primary"):
        # Persist the full context. We write BOTH the widget keys (some of
        # which Streamlit may preserve directly across nav) and the canonical
        # keys (which require_data / persist_sidebar_selectbox use to
        # restore the widget when its state has been GC'd).
        st.session_state["_canon_league"] = league
        st.session_state["_canon_competition"] = comp
        st.session_state["_canon_team"] = team
        st.session_state["selected_league"] = league
        st.session_state["selected_competition"] = comp
        st.session_state["selected_team"] = team
        st.switch_page("pages/2_Team_Detail.py")


@st.dialog("Player summary", width="large")
def _player_modal(league: str, comp: str, team: str, player: str) -> None:
    ps = load_player_season(league, comp)
    ap = load_appearances(league, comp)

    rows = ps[(ps.team == team) & (ps.player == player)]
    if rows.empty:
        st.error(f"Player {player!r} not found for {team!r}.")
        return
    row = rows.iloc[0]

    st.markdown(f"### {player}  ·  {row.position}  ·  {team}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Apps active", int(row.apps_active))
    c2.metric("Total active FV", f"{row.total_active_fv:.1f}")
    c3.metric(
        "Avg active FV",
        f"{row.avg_active_fv:.2f}" if pd.notna(row.avg_active_fv) else "—",
    )
    c4.metric(
        "% FV captured",
        f"{row.pct_fv_captured*100:.1f}%" if pd.notna(row.pct_fv_captured) else "—",
    )

    # Manager-usage verdict
    if pd.notna(row.avg_active_fv) and pd.notna(row.avg_fv_missed):
        delta = row.avg_active_fv - row.avg_fv_missed
        if delta > 0.3:
            color, label = "#2E7D32", "Well used"
            text = (f"Used in {player}'s better games "
                    f"(active avg {delta:+.2f} vs missed avg).")
        elif delta < -0.3:
            color, label = "#C62828", "Under used"
            text = (f"Missed {player}'s better games "
                    f"(active avg {delta:+.2f} vs missed avg).")
        else:
            color, label = "#777", "Balanced"
            text = f"Active and missed averages are close ({delta:+.2f})."
        st.markdown(
            f"<div style='padding:8px;border-left:4px solid {color};"
            f"background:#f7f7f7;margin:6px 0;'><b>{label}.</b> {text}</div>",
            unsafe_allow_html=True,
        )

    # Mini bar chart of fantavoto over time, coloured by active state
    me = ap[(ap.team == team) & (ap.player == player) & ap.fantavoto.notna()].copy()
    if not me.empty:
        me["bucket"] = me.active.map({True: "Active", False: "Missed"})
        fig = px.bar(
            me, x="giornata", y="fantavoto", color="bucket",
            color_discrete_map={"Active": ACTIVE_COLOR, "Missed": MISSED_COLOR},
            labels={"fantavoto": "FV", "giornata": "Giornata", "bucket": ""},
        )
        fig.update_layout(
            height=220, margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(dtick=2),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, width="stretch", key=f"player_modal_bars_{team}_{player}")

    if st.button(f"Open full Player Detail for {player} →",
                 width="stretch", type="primary"):
        # See _team_modal — both canonical and widget keys for resilience.
        st.session_state["_canon_league"] = league
        st.session_state["_canon_competition"] = comp
        st.session_state["_canon_team"] = team
        st.session_state["_canon_player"] = player
        st.session_state["selected_league"] = league
        st.session_state["selected_competition"] = comp
        st.session_state["selected_team"] = team
        st.session_state["selected_player"] = player
        st.switch_page("pages/3_Player_Detail.py")
